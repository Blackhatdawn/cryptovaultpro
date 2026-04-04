"""
Enhanced API Response Caching Decorator
Provides flexible caching for endpoints with TTL support
Integrates with Redis for distributed caching
"""

import hashlib
import json
import logging
from functools import wraps
from typing import Callable, Optional, Any, Union, List
from datetime import datetime, timedelta
import asyncio

from redis_cache import redis_cache
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class CacheConfig:
    """Configuration for endpoint caching"""
    
    def __init__(
        self,
        ttl_seconds: int = 300,
        cache_key_prefix: str = "api",
        vary_by: Optional[List[str]] = None,
        cache_on_status: List[int] = None,
    ):
        """
        Initialize cache configuration.
        
        Args:
            ttl_seconds: Time to live in seconds
            cache_key_prefix: Prefix for cache keys
            vary_by: Request parameters to include in cache key
            cache_on_status: HTTP status codes to cache (default: [200])
        """
        self.ttl_seconds = ttl_seconds
        self.cache_key_prefix = cache_key_prefix
        self.vary_by = vary_by or []
        self.cache_on_status = cache_on_status or [200]


# Pre-configured cache policies
CACHE_SHORT = CacheConfig(ttl_seconds=60, cache_key_prefix="cache:short")
CACHE_MEDIUM = CacheConfig(ttl_seconds=300, cache_key_prefix="cache:medium")
CACHE_LONG = CacheConfig(ttl_seconds=3600, cache_key_prefix="cache:long")
CACHE_PRICES = CacheConfig(
    ttl_seconds=60,
    cache_key_prefix="cache:prices",
    vary_by=["symbol", "currency"],
)
CACHE_USER_DATA = CacheConfig(
    ttl_seconds=600,
    cache_key_prefix="cache:user",
    vary_by=["user_id"],
)
CACHE_PORTFOLIO = CacheConfig(
    ttl_seconds=120,
    cache_key_prefix="cache:portfolio",
    vary_by=["user_id"],
)
CACHE_TRADING = CacheConfig(
    ttl_seconds=30,
    cache_key_prefix="cache:trading",
    vary_by=["pair", "interval"],
)
CACHE_ASSETS = CacheConfig(
    ttl_seconds=3600,
    cache_key_prefix="cache:assets",
)
CACHE_MARKET_DATA = CacheConfig(
    ttl_seconds=300,
    cache_key_prefix="cache:market",
    vary_by=["limit"],
)


def _generate_cache_key(
    prefix: str,
    func_name: str,
    args: tuple,
    kwargs: dict,
    vary_by: Optional[List[str]] = None,
) -> str:
    """Generate cache key from function arguments"""
    
    key_parts = [prefix, func_name]
    
    # Include specific kwargs in key if vary_by specified
    if vary_by:
        for param in vary_by:
            if param in kwargs:
                key_parts.append(f"{param}={kwargs[param]}")
    
    # Create hash of full key data
    key_str = ":".join(str(p) for p in key_parts)
    key_hash = hashlib.md5(key_str.encode()).hexdigest()[:8]
    
    return f"{key_str}:{key_hash}"


def cached_endpoint(
    config: CacheConfig = CACHE_MEDIUM,
    depends_on: Optional[List[str]] = None,
):
    """
    Decorator for caching API endpoint responses.
    
    Usage:
    @router.get("/prices")
    @cached_endpoint(CACHE_PRICES)
    async def get_prices(symbol: str):
        ...
    
    Args:
        config: CacheConfig instance
        depends_on: List of cache keys to invalidate when updated
    """
    
    def decorator(func: Callable) -> Callable:
        function_name = func.__name__
        cache_key_prefix = config.cache_key_prefix
        ttl_seconds = config.ttl_seconds
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            cache_key = _generate_cache_key(
                cache_key_prefix,
                function_name,
                args,
                kwargs,
                config.vary_by,
            )
            
            # Try to get from cache
            try:
                cached_value = await redis_cache.get(cache_key)
                if cached_value:
                    logger.debug(f"🎯 Cache HIT: {cache_key}")
                    return cached_value
            except Exception as e:
                logger.warning(f"⚠️  Cache retrieval failed: {str(e)}. Proceeding...")
            
            # Execute function
            logger.debug(f"❌ Cache MISS: {cache_key}")
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Cache successful responses
            try:
                # Check status code if response is JSONResponse
                should_cache = True
                if isinstance(result, JSONResponse):
                    if result.status_code not in config.cache_on_status:
                        should_cache = False
                
                if should_cache:
                    await redis_cache.set(cache_key, result, ttl_seconds)
                    logger.debug(f"💾 Cached: {cache_key} (TTL: {ttl_seconds}s)")
            
            except Exception as e:
                logger.warning(f"⚠️  Cache storage failed: {str(e)}. Continuing...")
            
            return result
        
        # Store metadata for invalidation
        wrapper.cache_config = config
        wrapper.cache_depends_on = depends_on or []
        wrapper.cache_key_prefix = cache_key_prefix
        
        return wrapper
    
    return decorator


async def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate cache entries matching pattern.
    
    Args:
        pattern: Pattern to match in cache keys
    
    Returns:
        Number of keys invalidated
    """
    try:
        count = await redis_cache.invalidate(pattern)
        logger.info(f"🧹 Invalidated {count} cache entries matching '{pattern}'")
        return count
    except Exception as e:
        logger.error(f"❌ Cache invalidation failed: {str(e)}")
        return 0


async def cache_warmer(
    cache_key: str,
    value: Any,
    ttl_seconds: int = 3600,
) -> None:
    """
    Pre-populate cache with value (cache warming).
    Useful for expensive operations that should always have fresh data.
    
    Args:
        cache_key: Cache key to use
        value: Value to cache
        ttl_seconds: Time to live
    """
    try:
        await redis_cache.set(cache_key, value, ttl_seconds)
        logger.info(f"🔥 Cache warmed: {cache_key}")
    except Exception as e:
        logger.error(f"❌ Cache warming failed: {str(e)}")


class CacheStats:
    """Track cache performance metrics"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.invalidations = 0
    
    def record_hit(self):
        """Record cache hit"""
        self.hits += 1
    
    def record_miss(self):
        """Record cache miss"""
        self.misses += 1
    
    def record_error(self):
        """Record cache error"""
        self.errors += 1
    
    def record_invalidation(self):
        """Record cache invalidation"""
        self.invalidations += 1
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "invalidations": self.invalidations,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total,
        }
    
    def reset(self):
        """Reset statistics"""
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.invalidations = 0


# Global cache stats
cache_stats = CacheStats()


def get_cache_headers(ttl_seconds: int) -> dict:
    """
    Generate HTTP cache headers for given TTL.
    
    Args:
        ttl_seconds: Time to live in seconds
    
    Returns:
        Dictionary of cache headers
    """
    stale_while_revalidate = max(ttl_seconds, 60)
    
    return {
        "Cache-Control": f"public, max-age={ttl_seconds}, stale-while-revalidate={stale_while_revalidate}",
        "Expires": (datetime.utcnow() + timedelta(seconds=ttl_seconds)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
    }


async def cache_control_header_middleware(request, call_next):
    """
    Middleware to automatically add cache control headers based on endpoint config.
    Use in fastapi app: app.middleware("http")(cache_control_header_middleware)
    """
    response = await call_next(request)
    
    # Add ETag for cache validation
    try:
        body = response.body
        etag = hashlib.md5(body).hexdigest()
        response.headers["ETag"] = f'"{etag}"'
        
        # Add vary header for cache busting
        response.headers["Vary"] = "Accept-Encoding"
    
    except Exception as e:
        logger.debug(f"Could not add ETag: {str(e)}")
    
    return response
