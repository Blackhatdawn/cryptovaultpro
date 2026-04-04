"""
Request Retry Logic with Exponential Backoff
Handles transient failures gracefully
Implements jitter to prevent thundering herd
"""

import asyncio
import logging
import random
from typing import Callable, Optional, Type, Tuple, Any
from functools import wraps

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_ms: int = 100,
        max_delay_ms: int = 10000,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        ),
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of attempts (including initial)
            initial_delay_ms: Initial delay in milliseconds
            max_delay_ms: Maximum delay between retries
            exponential_base: Multiplier for exponential backoff
            jitter: Add random jitter to prevent thundering herd
            retryable_exceptions: Exceptions that trigger retry
        """
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
    
    def get_delay_ms(self, attempt: int) -> int:
        """Calculate delay for given attempt (0-indexed)"""
        if attempt == 0:
            return 0  # No delay for first attempt
        
        # Exponential backoff: base^attempt
        delay = self.initial_delay_ms * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay_ms)
        
        # Add jitter: ±10%
        if self.jitter:
            jitter_amount = delay * 0.1
            delay = delay + random.uniform(-jitter_amount, jitter_amount)
        
        return max(1, int(delay))


# Pre-configured retry policies
RETRY_DEFAULT = RetryConfig(max_attempts=3)
RETRY_AGGRESSIVE = RetryConfig(max_attempts=5, initial_delay_ms=50)
RETRY_CONSERVATIVE = RetryConfig(max_attempts=2, initial_delay_ms=200)
RETRY_API = RetryConfig(
    max_attempts=4,
    initial_delay_ms=100,
    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
)


class RetryableException(Exception):
    """Base exception for retry logic"""
    pass


async def retry_with_backoff(
    func: Callable,
    *args,
    config: RetryConfig = RETRY_DEFAULT,
    name: str = "",
    **kwargs
) -> Any:
    """
    Execute async function with retry logic and exponential backoff.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: RetryConfig instance
        name: Name for logging
        **kwargs: Keyword arguments for func
    
    Returns:
        Result of function
    
    Raises:
        Last exception if all attempts fail
    """
    
    last_error = None
    
    for attempt in range(config.max_attempts):
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            if attempt > 0:
                logger.info(
                    f"✅ [{name or func.__name__}] Success on attempt {attempt + 1}/{config.max_attempts}"
                )
            
            return result
        
        except config.retryable_exceptions as e:
            last_error = e
            
            if attempt < config.max_attempts - 1:
                delay_ms = config.get_delay_ms(attempt + 1)
                logger.warning(
                    f"⚠️  [{name or func.__name__}] Attempt {attempt + 1} failed: {type(e).__name__}. "
                    f"Retrying in {delay_ms}ms... ({attempt + 1}/{config.max_attempts})"
                )
                await asyncio.sleep(delay_ms / 1000.0)
            else:
                logger.error(
                    f"❌ [{name or func.__name__}] All {config.max_attempts} attempts failed. "
                    f"Last error: {type(e).__name__}: {str(e)}"
                )
    
    raise last_error


def with_retry(
    config: RetryConfig = RETRY_DEFAULT,
    name: Optional[str] = None,
):
    """
    Decorator for async functions with automatic retry logic.
    
    Usage:
    @with_retry(RETRY_API)
    async def fetch_data():
        ...
    
    Or with custom config:
    @with_retry(RetryConfig(max_attempts=5))
    async def fetch_data():
        ...
    """
    def decorator(func: Callable) -> Callable:
        function_name = name or func.__name__
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await retry_with_backoff(
                func,
                *args,
                config=config,
                name=function_name,
                **kwargs,
            )
        
        return wrapper
    return decorator


class RetryStats:
    """Track retry statistics across application"""
    
    def __init__(self):
        self.total_attempts = 0
        self.successful_retries = 0  # Succeeded after initial failure
        self.failed_retries = 0       # Failed all attempts
        self.retry_by_exception = {}
    
    def record_attempt(self, exception: Optional[Exception] = None, success: bool = False):
        """Record an attempt"""
        self.total_attempts += 1
        
        if exception:
            exc_type = type(exception).__name__
            self.retry_by_exception[exc_type] = self.retry_by_exception.get(exc_type, 0) + 1
            
            if success:
                self.successful_retries += 1
            else:
                self.failed_retries += 1
    
    def get_stats(self) -> dict:
        """Get retry statistics"""
        return {
            "total_attempts": self.total_attempts,
            "successful_retries": self.successful_retries,
            "failed_retries": self.failed_retries,
            "success_rate": (
                self.successful_retries / self.total_attempts
                if self.total_attempts > 0
                else 0
            ),
            "by_exception": self.retry_by_exception,
        }
    
    def reset(self):
        """Reset statistics"""
        self.total_attempts = 0
        self.successful_retries = 0
        self.failed_retries = 0
        self.retry_by_exception = {}


# Global retry stats
retry_stats = RetryStats()


# HTTP status codes that should trigger retries
RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}


async def retry_http_request(
    make_request: Callable,
    *args,
    config: RetryConfig = RETRY_API,
    name: str = "HTTP Request",
    status_codes_to_retry: set = RETRYABLE_HTTP_STATUS,
    **kwargs,
) -> Any:
    """
    Retry HTTP request based on status codes.
    
    Args:
        make_request: Async function that makes HTTP request
        *args: Arguments for make_request
        config: RetryConfig
        name: Request name for logging
        status_codes_to_retry: HTTP status codes to retry on
        **kwargs: Keyword arguments for make_request
    
    Returns:
        Response object
    """
    
    last_error = None
    
    for attempt in range(config.max_attempts):
        try:
            response = await make_request(*args, **kwargs)
            
            # Check if response status code should trigger retry
            if hasattr(response, 'status_code') and response.status_code in status_codes_to_retry:
                if attempt < config.max_attempts - 1:
                    delay_ms = config.get_delay_ms(attempt + 1)
                    logger.warning(
                        f"⚠️  [{name}] HTTP {response.status_code}. "
                        f"Retrying in {delay_ms}ms... ({attempt + 1}/{config.max_attempts})"
                    )
                    await asyncio.sleep(delay_ms / 1000.0)
                    continue
            
            if attempt > 0:
                logger.info(f"✅ [{name}] Success after {attempt + 1} attempts")
            
            return response
        
        except Exception as e:
            last_error = e
            
            if attempt < config.max_attempts - 1:
                delay_ms = config.get_delay_ms(attempt + 1)
                logger.warning(
                    f"⚠️  [{name}] Attempt {attempt + 1} failed: {type(e).__name__}. "
                    f"Retrying in {delay_ms}ms..."
                )
                await asyncio.sleep(delay_ms / 1000.0)
            else:
                logger.error(f"❌ [{name}] All {config.max_attempts} attempts failed")
    
    raise last_error
