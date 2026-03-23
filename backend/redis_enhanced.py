"""
Enhanced Redis Service with Pub/Sub, Lua Scripts, and Atomic Operations
Builds upon the existing redis_cache.py with advanced production features.
"""
import logging
import json
import asyncio
from typing import Optional, Any, Dict, List, Callable
import httpx
from config import settings

logger = logging.getLogger(__name__)


class RedisEnhanced:
    """
    Enhanced Redis service with pub/sub, Lua scripts, and atomic operations.
    Uses Upstash REST API for serverless Redis operations.
    Auto-disables on repeated failures to prevent log spam.
    """
    
    def __init__(self):
        self.use_redis = settings.is_redis_available()
        self.redis_url = settings.upstash_redis_rest_url
        self.redis_token = settings.upstash_redis_rest_token
        self._consecutive_failures = 0
        self._max_failures = 3
        
        # Pub/Sub subscribers
        self.subscribers: Dict[str, List[Callable]] = {}
        self.pubsub_task: Optional[asyncio.Task] = None
        
        # Lua scripts (registered on first use)
        self.lua_scripts = {
            "get_or_set": """
                local value = redis.call('GET', KEYS[1])
                if value then
                    return value
                else
                    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
                    return ARGV[1]
                end
            """,
            "increment_with_ttl": """
                local current = redis.call('INCR', KEYS[1])
                if current == 1 then
                    redis.call('EXPIRE', KEYS[1], ARGV[1])
                end
                return current
            """,
            "atomic_update": """
                local old_value = redis.call('GET', KEYS[1])
                redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
                return old_value
            """
        }
        
        logger.info(f"Enhanced Redis initialized (enabled={self.use_redis})")
    
    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._max_failures and self.use_redis:
            logger.warning(f"Enhanced Redis disabled after {self._consecutive_failures} consecutive failures.")
            self.use_redis = False

    def _record_success(self):
        self._consecutive_failures = 0
    
    # ============================================
    # PUB/SUB OPERATIONS
    # ============================================
    
    async def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        Publish message to Redis channel.
        Used for broadcasting real-time updates (prices, notifications, etc.)
        """
        if not self.use_redis:
            logger.debug(f"Redis disabled, skipping publish to {channel}")
            return False
        
        try:
            message_json = json.dumps(message)
            
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    self.redis_url,
                    headers={
                        "Authorization": f"Bearer {self.redis_token}",
                        "Content-Type": "application/json"
                    },
                    json=["PUBLISH", channel, message_json]
                )
                
                if response.status_code == 200:
                    self._record_success()
                    logger.debug(f"Published to {channel}")
                    return True
                else:
                    self._record_failure()
                    return False
        
        except Exception as e:
            self._record_failure()
            return False
    
    async def subscribe(self, channel: str, callback: Callable[[Dict], None]):
        """
        Subscribe to Redis channel.
        Note: Upstash REST API doesn't support persistent subscriptions.
        This is a simplified implementation for demonstration.
        For production pub/sub, consider using Upstash Redis with native protocol.
        """
        if channel not in self.subscribers:
            self.subscribers[channel] = []
        
        self.subscribers[channel].append(callback)
        logger.info(f"📡 Subscribed to channel: {channel}")
    
    def unsubscribe(self, channel: str, callback: Callable):
        """Unsubscribe from Redis channel."""
        if channel in self.subscribers and callback in self.subscribers[channel]:
            self.subscribers[channel].remove(callback)
            logger.info(f"📡 Unsubscribed from channel: {channel}")
    
    async def broadcast_update(self, event_type: str, data: Dict[str, Any]):
        """
        Broadcast update to all subscribers.
        Common event types: 'price_update', 'order_filled', 'notification'
        """
        channel = f"updates:{event_type}"
        message = {
            "type": event_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.publish(channel, message)
        
        # Notify local subscribers (in-memory)
        if channel in self.subscribers:
            for callback in self.subscribers[channel]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Subscriber callback error: {e}")
    
    # ============================================
    # LUA SCRIPT OPERATIONS
    # ============================================
    
    async def execute_lua(self, script: str, keys: List[str], args: List[str]) -> Any:
        """
        Execute Lua script on Redis.
        Note: Upstash REST API supports EVAL command.
        """
        if not self.use_redis:
            return None
        
        try:
            import urllib.parse
            
            # Construct EVAL command
            # Format: EVAL script numkeys key [key ...] arg [arg ...]
            script_encoded = urllib.parse.quote(script)
            numkeys = len(keys)
            
            # Build command parts
            command_parts = ["EVAL", script_encoded, str(numkeys)]
            command_parts.extend(keys)
            command_parts.extend(args)
            
            # Join with slashes for REST API
            command_url = "/".join(command_parts)
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.redis_url}/{command_url}",
                    headers={"Authorization": f"Bearer {self.redis_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result")
                else:
                    logger.warning(f"Lua script execution failed: {response.status_code}")
                    return None
        
        except Exception as e:
            logger.error(f"❌ Lua script error: {str(e)}")
            return None
    
    async def get_or_set_atomic(self, key: str, value: Any, ttl: int = 300) -> Any:
        """
        Atomically get a key, or set it if it doesn't exist.
        Returns the existing or newly set value.
        """
        if not self.use_redis:
            return value
        
        value_json = json.dumps(value) if not isinstance(value, str) else value
        
        result = await self.execute_lua(
            self.lua_scripts["get_or_set"],
            keys=[key],
            args=[value_json, str(ttl)]
        )
        
        if result:
            try:
                return json.loads(result)
            except (json.JSONDecodeError, TypeError):
                return result
        
        return value
    
    async def increment_with_expiry(self, key: str, ttl: int = 60) -> int:
        """
        Atomically increment counter and set TTL on first increment.
        Useful for rate limiting.
        """
        if not self.use_redis:
            return 1
        
        result = await self.execute_lua(
            self.lua_scripts["increment_with_ttl"],
            keys=[key],
            args=[str(ttl)]
        )
        
        return int(result) if result else 1
    
    async def atomic_swap(self, key: str, new_value: Any, ttl: int = 300) -> Optional[Any]:
        """
        Atomically swap value and return old value.
        Useful for cache invalidation with history.
        """
        if not self.use_redis:
            return None
        
        new_value_json = json.dumps(new_value) if not isinstance(new_value, str) else new_value
        
        old_value = await self.execute_lua(
            self.lua_scripts["atomic_update"],
            keys=[key],
            args=[new_value_json, str(ttl)]
        )
        
        if old_value:
            try:
                return json.loads(old_value)
            except (json.JSONDecodeError, TypeError):
                return old_value
        
        return None
    
    # ============================================
    # SESSION & TOKEN MANAGEMENT
    # ============================================
    
    async def store_refresh_token(self, user_id: str, token: str, ttl: int = 604800) -> bool:
        """
        Store JWT refresh token in Redis with TTL (default 7 days).
        Key format: refresh_token:{user_id}:{token_id}
        """
        if not self.use_redis:
            return False
        
        key = f"refresh_token:{user_id}"
        token_data = {
            "token": token,
            "created_at": asyncio.get_event_loop().time(),
            "user_id": user_id
        }
        
        try:
            value = json.dumps(token_data)
            
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
                    logger.debug(f"Stored refresh token for user {user_id}")
                    return True
        
        except Exception as e:
            logger.error(f"Failed to store refresh token: {str(e)}")
        
        return False
    
    async def get_refresh_token(self, user_id: str) -> Optional[Dict]:
        """Retrieve refresh token data from Redis."""
        if not self.use_redis:
            return None
        
        key = f"refresh_token:{user_id}"
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.redis_url}/get/{key}",
                    headers={"Authorization": f"Bearer {self.redis_token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result")
                    
                    if result:
                        try:
                            return json.loads(result)
                        except (json.JSONDecodeError, TypeError):
                            return None
        
        except Exception as e:
            logger.error(f"❌ Failed to get refresh token: {str(e)}")
        
        return None
    
    async def invalidate_refresh_token(self, user_id: str) -> bool:
        """Invalidate refresh token (logout)."""
        if not self.use_redis:
            return False
        
        key = f"refresh_token:{user_id}"
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self.redis_url}/del/{key}",
                    headers={"Authorization": f"Bearer {self.redis_token}"}
                )
                
                if response.status_code == 200:
                    logger.info(f"🔒 Invalidated refresh token for user {user_id}")
                    return True
        
        except Exception as e:
            logger.error(f"❌ Failed to invalidate refresh token: {str(e)}")
        
        return False
    
    # ============================================
    # CACHE INVALIDATION HELPERS
    # ============================================
    
    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache entries for a user and broadcast update."""
        patterns = [
            f"user:{user_id}",
            f"portfolio:{user_id}",
            f"wallet:{user_id}",
            f"orders:{user_id}"
        ]
        
        # Delete from Redis
        for pattern in patterns:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(
                        f"{self.redis_url}/del/{pattern}",
                        headers={"Authorization": f"Bearer {self.redis_token}"}
                    )
            except Exception as e:
                logger.warning(f"Cache invalidation warning: {e}")
        
        # Broadcast cache invalidation
        await self.broadcast_update("cache_invalidation", {
            "user_id": user_id,
            "patterns": patterns
        })
        
        logger.info(f"🗑️ Invalidated cache for user {user_id}")
    
    async def invalidate_price_cache(self, symbols: List[str]):
        """Invalidate price cache and broadcast price update."""
        for symbol in symbols:
            key = f"price:{symbol.lower()}"
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(
                        f"{self.redis_url}/del/{key}",
                        headers={"Authorization": f"Bearer {self.redis_token}"}
                    )
            except Exception:
                pass
        
        await self.broadcast_update("price_invalidation", {
            "symbols": symbols
        })
        
        logger.debug(f"🗑️ Invalidated price cache for {len(symbols)} symbols")


# Global enhanced Redis instance
redis_enhanced = RedisEnhanced()
