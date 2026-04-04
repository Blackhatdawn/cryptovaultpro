"""
Circuit Breaker Pattern Implementation
Prevents cascading failures when external services are down
Implements exponential backoff and automatic recovery
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for managing external API calls.
    Prevents cascading failures when services are down.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests fail immediately
    - HALF_OPEN: Testing recovery, allowing trial requests
    
    Parameters:
    - failure_threshold: Number of failures before opening (default: 5)
    - success_threshold: Number of successes in HALF_OPEN before closing (default: 2)
    - timeout: Seconds before transitioning OPEN→HALF_OPEN (default: 60)
    - name: Circuit breaker identifier
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.utcnow()
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_rejections = 0
        self.state_changes_log = []
    
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)"""
        return self.state == CircuitState.CLOSED
    
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)"""
        return self.state == CircuitState.OPEN
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (recovery mode)"""
        return self.state == CircuitState.HALF_OPEN
    
    def can_attempt_request(self) -> bool:
        """Determine if a request should be attempted"""
        if self.is_closed():
            return True
        
        if self.is_open():
            # Check if timeout elapsed to transition to HALF_OPEN
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed >= self.timeout_seconds:
                self._transition_to_half_open()
                return True
            return False
        
        if self.is_half_open():
            # Allow requests in HALF_OPEN to test recovery
            return True
        
        return False
    
    def record_success(self) -> None:
        """Record a successful request"""
        self.total_calls += 1
        
        if self.is_closed():
            # Reset failure count on success in normal operation
            self.failure_count = 0
        
        elif self.is_half_open():
            self.success_count += 1
            logger.info(
                f"🔌 [{self.name}] HALF_OPEN success: {self.success_count}/{self.success_threshold}"
            )
            
            # Transition to CLOSED if threshold reached
            if self.success_count >= self.success_threshold:
                self._transition_to_closed()
    
    def record_failure(self) -> None:
        """Record a failed request"""
        self.total_calls += 1
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.is_closed():
            logger.warning(
                f"🔌 [{self.name}] CLOSED failure: {self.failure_count}/{self.failure_threshold}"
            )
            
            # Transition to OPEN if threshold reached
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()
        
        elif self.is_half_open():
            logger.warning(f"🔌 [{self.name}] HALF_OPEN failure, reverting to OPEN")
            self._transition_to_open()
    
    def record_rejection(self) -> None:
        """Record a rejected request (circuit open)"""
        self.total_calls += 1
        self.total_rejections += 1
    
    def _transition_to_open(self) -> None:
        """Transition to OPEN state"""
        self.state = CircuitState.OPEN
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.utcnow()
        self.state_changes_log.append((datetime.utcnow(), CircuitState.OPEN))
        logger.error(f"🔴 [{self.name}] Circuit OPENED (failing fast)")
    
    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state"""
        self.state = CircuitState.HALF_OPEN
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.utcnow()
        self.state_changes_log.append((datetime.utcnow(), CircuitState.HALF_OPEN))
        logger.info(f"🟡 [{self.name}] Circuit HALF_OPEN (testing recovery)")
    
    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.utcnow()
        self.state_changes_log.append((datetime.utcnow(), CircuitState.CLOSED))
        logger.info(f"🟢 [{self.name}] Circuit CLOSED (recovered)")
    
    def get_metrics(self) -> dict:
        """Get circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_rejections": self.total_rejections,
            "failure_rate": (
                self.total_failures / self.total_calls if self.total_calls > 0 else 0
            ),
            "rejection_rate": (
                self.total_rejections / self.total_calls if self.total_calls > 0 else 0
            ),
            "time_in_current_state": (
                datetime.utcnow() - self.last_state_change
            ).total_seconds(),
        }
    
    def reset(self) -> None:
        """Reset circuit breaker to closed state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.utcnow()
        logger.info(f"🔄 [{self.name}] Circuit reset to CLOSED")


class CircuitBreakerRegistry:
    """Registry of circuit breakers for monitoring external services"""
    
    _breakers: dict[str, CircuitBreaker] = {}
    
    @classmethod
    def create(
        cls,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
    ) -> CircuitBreaker:
        """Create or get existing circuit breaker"""
        if name not in cls._breakers:
            cls._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                success_threshold=success_threshold,
                timeout_seconds=timeout_seconds,
            )
        return cls._breakers[name]
    
    @classmethod
    def get(cls, name: str) -> Optional[CircuitBreaker]:
        """Get existing circuit breaker"""
        return cls._breakers.get(name)
    
    @classmethod
    def get_all(cls) -> dict[str, CircuitBreaker]:
        """Get all circuit breakers"""
        return cls._breakers.copy()
    
    @classmethod
    def reset_all(cls) -> None:
        """Reset all circuit breakers"""
        for breaker in cls._breakers.values():
            breaker.reset()
    
    @classmethod
    def get_metrics(cls) -> dict[str, dict]:
        """Get metrics for all circuit breakers"""
        return {name: breaker.get_metrics() for name, breaker in cls._breakers.items()}


# Pre-configured breakers for common external services
BREAKER_COINCAP = CircuitBreakerRegistry.create("coincap-api", failure_threshold=5, timeout_seconds=60)
BREAKER_COINMARKETCAP = CircuitBreakerRegistry.create("coinmarketcap-api", failure_threshold=5, timeout_seconds=60)
BREAKER_FIREBASE = CircuitBreakerRegistry.create("firebase", failure_threshold=3, timeout_seconds=30)
BREAKER_EMAIL = CircuitBreakerRegistry.create("email-service", failure_threshold=3, timeout_seconds=60)
BREAKER_TELEGRAM = CircuitBreakerRegistry.create("telegram-bot", failure_threshold=5, timeout_seconds=120)
BREAKER_NOWPAYMENTS = CircuitBreakerRegistry.create("nowpayments-api", failure_threshold=5, timeout_seconds=60)


def with_circuit_breaker(
    breaker: CircuitBreaker,
    fallback: Optional[Callable] = None,
):
    """
    Decorator to add circuit breaker protection to async functions
    
    Usage:
    @with_circuit_breaker(BREAKER_COINCAP, fallback=fallback_function)
    async def fetch_prices():
        ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            if not breaker.can_attempt_request():
                breaker.record_rejection()
                logger.warning(
                    f"🔴 [{breaker.name}] Request rejected (circuit {breaker.state.value})"
                )
                
                if fallback:
                    return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                
                raise Exception(f"Service unavailable: {breaker.name}")
            
            try:
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                breaker.record_success()
                return result
            
            except Exception as e:
                breaker.record_failure()
                logger.error(f"🔴 [{breaker.name}] Request failed: {str(e)}")
                
                if fallback:
                    return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                
                raise
        
        return wrapper
    return decorator
