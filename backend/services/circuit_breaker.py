"""
Circuit Breaker Pattern Implementation
Protects against cascading failures from external API calls
"""

import time
import asyncio
from typing import Callable, Optional, Any
from enum import Enum
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for external API calls
    
    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Too many failures, reject all requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.half_open_attempts = 0
        
        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"threshold={failure_threshold}, timeout={recovery_timeout}s"
        )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.state == CircuitState.OPEN and self.last_failure_time:
            elapsed = time.time() - self.last_failure_time
            return elapsed >= self.recovery_timeout
        return False
    
    def _record_success(self):
        """Record successful call"""
        self.failure_count = 0
        self.half_open_attempts = 0
        
        if self.state != CircuitState.CLOSED:
            logger.info(f"Circuit breaker '{self.name}' recovered - closing circuit")
            self.state = CircuitState.CLOSED
    
    def _record_failure(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test - reopen circuit
            logger.warning(
                f"Circuit breaker '{self.name}' failed recovery test - reopening"
            )
            self.state = CircuitState.OPEN
            
        elif self.failure_count >= self.failure_threshold:
            # Too many failures - open circuit
            logger.error(
                f"Circuit breaker '{self.name}' opened after {self.failure_count} failures"
            )
            self.state = CircuitState.OPEN
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to call
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Original exception: If function fails
        """
        # Check if we should attempt reset
        if self._should_attempt_reset():
            logger.info(f"Circuit breaker '{self.name}' attempting recovery (half-open)")
            self.state = CircuitState.HALF_OPEN
            self.half_open_attempts = 0
        
        # Reject if circuit is open
        if self.state == CircuitState.OPEN:
            logger.warning(f"Circuit breaker '{self.name}' is open - rejecting request")
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open. "
                f"Service unavailable. Retry after {self.recovery_timeout}s"
            )
        
        # Limit attempts in half-open state
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_attempts >= 3:
                logger.warning(
                    f"Circuit breaker '{self.name}' half-open limit reached"
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is testing recovery. "
                    f"Please retry in a moment."
                )
            self.half_open_attempts += 1
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            logger.error(
                f"Circuit breaker '{self.name}' recorded failure: {str(e)}"
            )
            raise
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# ============================================
# GLOBAL CIRCUIT BREAKERS
# ============================================

# CoinCap API (Primary price source - 200 req/min free tier)
coincap_breaker = CircuitBreaker(
    name="coincap",
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

# CoinPaprika API (Fallback price source - free, no auth)
coinpaprika_breaker = CircuitBreaker(
    name="coinpaprika",
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

# NowPayments API
nowpayments_breaker = CircuitBreaker(
    name="nowpayments",
    failure_threshold=3,
    recovery_timeout=120,
    expected_exception=Exception
)

# SendGrid Email
sendgrid_breaker = CircuitBreaker(
    name="sendgrid",
    failure_threshold=3,
    recovery_timeout=120,
    expected_exception=Exception
)


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_all_breakers() -> dict:
    """Get state of all circuit breakers"""
    return {
        "coincap": coincap_breaker.get_state(),
        "coinpaprika": coinpaprika_breaker.get_state(),
        "nowpayments": nowpayments_breaker.get_state(),
        "sendgrid": sendgrid_breaker.get_state(),
    }


async def reset_breaker(name: str) -> bool:
    """Manually reset a circuit breaker"""
    breakers = {
        "coincap": coincap_breaker,
        "coinpaprika": coinpaprika_breaker,
        "nowpayments": nowpayments_breaker,
        "sendgrid": sendgrid_breaker,
    }
    
    if name in breakers:
        breaker = breakers[name]
        breaker.failure_count = 0
        breaker.state = CircuitState.CLOSED
        logger.info(f"Circuit breaker '{name}' manually reset")
        return True
    
    return False
