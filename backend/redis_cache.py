"""
Redis Caching Service using Upstash Redis (REST API)
Provides caching for prices, rate limiting, and session management
Falls back to in-memory cache if Redis is unavailable
"""
import logging
import json
import time
from typing import Optional, Any, Dict
from datetime import timedelta
import httpx
from config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis caching service with Upstash REST API.
    Gracefully falls back to in-memory caching if Redis is unavailable.
    Auto-disables on repeated failures to prevent log spam.
    """
    
    def __init__(self):
        self.use_redis = settings.is_redis_available()
        self.redis_url = settings.upstash_redis_rest_url
        self.redis_token = settings.upstash_redis_rest_token
        self._consecutive_failures = 0
        self._max_failures = 3  # Auto-disable after 3 consecutive failures
        
        # In-memory fallback cache
        self.memory_cache: Dict[str, tuple[Any, float]] = {}
        
        # Cache TTLs (in seconds)
        self.DEFAULT_TTL = 300  # 5 minutes
        self.PRICE_TTL = 60  # 1 minute for prices
        self.SESSION_TTL = 3600  # 1 hour for sessions
        
        logger.info(f"Redis Cache initialized (redis={self.use_redis})")
    
    def _record_failure(self):
        """Track consecutive Redis failures and auto-disable if threshold hit."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._max_failures and self.use_redis:
            logger.warning(f"Redis disabled after {self._consecutive_failures} consecutive failures. Using in-memory cache.")
            self.use_redis = False

    def _record_success(self):
        """Reset failure counter on successful Redis operation."""
        self._consecutive_failures = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self.use_redis:
            return await self._get_redis(key)
        else:
            return self._get_memory(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL (seconds)."""
        if self.use_redis:
            return await self._set_redis(key, value, ttl or self.DEFAULT_TTL)
        else:
            return self._set_memory(key, value, ttl or self.DEFAULT_TTL)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if self.use_redis:
            return await self._delete_redis(key)
        else:
            return self._delete_memory(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        value = await self.get(key)
        return value is not None
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        if self.use_redis:
            return await self._incr_redis(key, amount)
        else:
            return self._incr_memory(key, amount)
    
    async def set_with_expiry(self, key: str, value: Any, seconds: int) -> bool:
        """Set value with expiry time."""
        return await self.set(key, value, seconds)
    
    # ============================================
    # REDIS OPERATIONS (Upstash REST API)
    # ============================================
    
    async def _get_redis(self, key: str) -> Optional[Any]:
        """Get from Redis via REST API."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.redis_url}/get/{key}",
                    headers={"Authorization": f"Bearer {self.redis_token}"}
                )
                
                if response.status_code == 200:
                    self._record_success()
                    data = response.json()
                    result = data.get("result")
                    
                    if result is None:
                        return None
                    
                    try:
                        parsed = json.loads(result)
                        if isinstance(parsed, str):
                            try:
                                return json.loads(parsed)
                            except (json.JSONDecodeError, TypeError):
                                return parsed
                        return parsed
                    except (json.JSONDecodeError, TypeError):
                        return result
                
                self._record_failure()
                return self._get_memory(key)
                
        except Exception as e:
            self._record_failure()
            return self._get_memory(key)
    
    async def _set_redis(self, key: str, value: Any, ttl: int) -> bool:
        """Set in Redis via REST API with TTL."""
        try:
            if not isinstance(value, str):
                value = json.dumps(value)
            
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    self.redis_url,
                    headers={
                        "Authorization": f"Bearer {self.redis_token}",
                        "Content-Type": "application/json"
                    },
                    json=["SETEX", key, str(ttl), value]
                )
                
                if response.status_code == 200:
                    self._record_success()
                    return True
                self._record_failure()
                return self._set_memory(key, value, ttl)
                
        except Exception as e:
            self._record_failure()
            return self._set_memory(key, value, ttl)
    
    async def _delete_redis(self, key: str) -> bool:
        """Delete from Redis via REST API."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self.redis_url}/del/{key}",
                    headers={"Authorization": f"Bearer {self.redis_token}"}
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.warning(f"⚠️ Redis DEL error for '{key}': {str(e)}")
            return self._delete_memory(key)
    
    async def _incr_redis(self, key: str, amount: int) -> int:
        """Increment counter in Redis."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self.redis_url}/incrby/{key}/{amount}",
                    headers={"Authorization": f"Bearer {self.redis_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", 0)
                
                return 0
                
        except Exception as e:
            logger.warning(f"⚠️ Redis INCR error for '{key}': {str(e)}")
            return self._incr_memory(key, amount)
    
    # ============================================
    # IN-MEMORY FALLBACK OPERATIONS
    # ============================================
    
    def _get_memory(self, key: str) -> Optional[Any]:
        """Get from memory cache."""
        if key in self.memory_cache:
            value, expiry = self.memory_cache[key]
            if time.time() < expiry:
                return value
            else:
                # Expired
                del self.memory_cache[key]
        return None
    
    def _set_memory(self, key: str, value: Any, ttl: int) -> bool:
        """Set in memory cache with TTL."""
        expiry = time.time() + ttl
        self.memory_cache[key] = (value, expiry)
        
        # Cleanup old entries (simple approach)
        if len(self.memory_cache) > 1000:
            self._cleanup_memory()
        
        return True
    
    def _delete_memory(self, key: str) -> bool:
        """Delete from memory cache."""
        if key in self.memory_cache:
            del self.memory_cache[key]
            return True
        return False
    
    def _incr_memory(self, key: str, amount: int) -> int:
        """Increment counter in memory."""
        current = self._get_memory(key) or 0
        try:
            new_value = int(current) + amount
        except (ValueError, TypeError):
            new_value = amount
        
        self._set_memory(key, new_value, self.DEFAULT_TTL)
        return new_value
    
    def _cleanup_memory(self):
        """Remove expired entries from memory cache."""
        now = time.time()
        expired_keys = [k for k, (_, expiry) in self.memory_cache.items() if expiry < now]
        for key in expired_keys:
            del self.memory_cache[key]
        
        logger.info(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
    
    # ============================================
    # HELPER METHODS FOR COMMON USE CASES
    # ============================================
    
    async def cache_prices(self, prices: list) -> bool:
        """Cache cryptocurrency prices."""
        return await self.set("crypto:prices", prices, self.PRICE_TTL)
    
    async def get_cached_prices(self) -> Optional[list]:
        """Get cached cryptocurrency prices."""
        return await self.get("crypto:prices")
    
    async def cache_coin_details(self, coin_id: str, data: dict) -> bool:
        """Cache individual coin details."""
        return await self.set(f"crypto:coin:{coin_id}", data, self.DEFAULT_TTL)
    
    async def get_cached_coin_details(self, coin_id: str) -> Optional[dict]:
        """Get cached coin details."""
        return await self.get(f"crypto:coin:{coin_id}")
    
    async def rate_limit_check(self, identifier: str, limit: int, window: int) -> bool:
        """
        Check if rate limit is exceeded.
        Returns True if allowed, False if limit exceeded.
        """
        key = f"ratelimit:{identifier}"
        current = await self.get(key) or 0
        
        if int(current) >= limit:
            return False
        
        await self.increment(key)
        
        # Set expiry on first increment
        if int(current) == 0:
            await self.set_with_expiry(key, 1, window)
        
        return True


# Global cache instance
redis_cache = RedisCache()
