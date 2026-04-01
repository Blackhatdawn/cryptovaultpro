"""
Enterprise WebSocket Connection Manager
Production-ready WebSocket management with security, monitoring, and scalability features.

Features:
- Connection limits (per-IP, per-user, total)
- Message rate limiting
- Connection health monitoring
- Graceful shutdown with connection draining
- Metrics collection for observability
- Memory-efficient connection tracking
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from weakref import WeakSet

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class ConnectionMetrics:
    """Metrics for a single connection."""
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    messages_sent: int = 0
    messages_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    websocket: WebSocket
    client_ip: str
    user_id: Optional[str] = None
    state: ConnectionState = ConnectionState.CONNECTING
    subscriptions: Set[str] = field(default_factory=set)
    metrics: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    rate_limit_tokens: float = 10.0  # Token bucket for rate limiting
    last_rate_refill: float = field(default_factory=time.time)


class RateLimiter:
    """Token bucket rate limiter for WebSocket messages."""
    
    def __init__(self, tokens_per_second: float = 10.0, max_tokens: float = 20.0):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
    
    def consume(self, info: ConnectionInfo, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        now = time.time()
        elapsed = now - info.last_rate_refill
        
        # Refill tokens based on elapsed time
        info.rate_limit_tokens = min(
            self.max_tokens,
            info.rate_limit_tokens + (elapsed * self.tokens_per_second)
        )
        info.last_rate_refill = now
        
        if info.rate_limit_tokens >= tokens:
            info.rate_limit_tokens -= tokens
            return True
        return False


class EnterpriseWebSocketManager:
    """
    Enterprise-grade WebSocket connection manager.
    
    Provides:
    - Connection lifecycle management
    - Security (rate limiting, connection limits)
    - Health monitoring
    - Metrics collection
    - Graceful shutdown
    """
    
    # Configuration defaults
    MAX_CONNECTIONS_PER_IP: int = 10
    MAX_CONNECTIONS_PER_USER: int = 5
    MAX_TOTAL_CONNECTIONS: int = 10000
    CONNECTION_TIMEOUT_SECONDS: int = 300  # 5 minutes idle
    MESSAGE_RATE_LIMIT: float = 10.0  # messages per second
    MAX_MESSAGE_SIZE: int = 65536  # 64KB
    HEALTH_CHECK_INTERVAL: int = 30  # seconds
    
    def __init__(
        self,
        max_connections_per_ip: int = None,
        max_connections_per_user: int = None,
        max_total_connections: int = None,
        message_rate_limit: float = None,
        connection_timeout: int = None
    ):
        # Configuration
        self.max_connections_per_ip = max_connections_per_ip or self.MAX_CONNECTIONS_PER_IP
        self.max_connections_per_user = max_connections_per_user or self.MAX_CONNECTIONS_PER_USER
        self.max_total_connections = max_total_connections or self.MAX_TOTAL_CONNECTIONS
        self.connection_timeout = connection_timeout or self.CONNECTION_TIMEOUT_SECONDS
        
        # Connection tracking
        self._connections: Dict[WebSocket, ConnectionInfo] = {}
        self._ip_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._user_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._channel_subscribers: Dict[str, Set[WebSocket]] = defaultdict(set)
        
        # Rate limiting
        self._rate_limiter = RateLimiter(
            tokens_per_second=message_rate_limit or self.MESSAGE_RATE_LIMIT
        )
        
        # Metrics
        self._total_connections_ever: int = 0
        self._total_messages_sent: int = 0
        self._total_messages_received: int = 0
        self._start_time: datetime = datetime.now(timezone.utc)
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_shutting_down: bool = False
        
        # Event callbacks
        self._on_connect_callbacks: List[Callable] = []
        self._on_disconnect_callbacks: List[Callable] = []
        self._on_message_callbacks: List[Callable] = []
        
        logger.info(
            f"🔌 EnterpriseWebSocketManager initialized "
            f"(max_per_ip={self.max_connections_per_ip}, "
            f"max_total={self.max_total_connections})"
        )
    
    # ============================================
    # CONNECTION LIFECYCLE
    # ============================================
    
    async def accept_connection(
        self,
        websocket: WebSocket,
        client_ip: Optional[str] = None
    ) -> bool:
        """
        Accept a new WebSocket connection with security checks.
        
        Returns True if connection was accepted, False if rejected.
        """
        if self._is_shutting_down:
            await websocket.close(code=1001, reason="Server shutting down")
            return False
        
        # Get client IP
        if client_ip is None:
            client_ip = self._get_client_ip(websocket)
        
        # Check connection limits
        if not self._check_connection_limits(client_ip):
            logger.warning(f"⚠️ Connection rejected for {client_ip}: limit exceeded")
            await websocket.close(code=4008, reason="Connection limit exceeded")
            return False
        
        # Accept the connection
        await websocket.accept()
        
        # Track the connection
        info = ConnectionInfo(
            websocket=websocket,
            client_ip=client_ip,
            state=ConnectionState.CONNECTED
        )
        self._connections[websocket] = info
        self._ip_connections[client_ip].add(websocket)
        self._total_connections_ever += 1
        
        logger.info(
            f"📡 WebSocket connected from {client_ip} "
            f"(total: {len(self._connections)})"
        )
        
        # Send welcome message
        await self.send_json(websocket, {
            "type": "connection",
            "status": "connected",
            "message": "Connected to CryptoVault WebSocket",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Trigger callbacks
        for callback in self._on_connect_callbacks:
            try:
                await callback(websocket, info)
            except Exception as e:
                logger.error(f"Connect callback error: {e}")
        
        return True
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Handle WebSocket disconnection with cleanup."""
        info = self._connections.pop(websocket, None)
        if info is None:
            return
        
        info.state = ConnectionState.CLOSED
        
        # Remove from IP tracking
        if info.client_ip in self._ip_connections:
            self._ip_connections[info.client_ip].discard(websocket)
            if not self._ip_connections[info.client_ip]:
                del self._ip_connections[info.client_ip]
        
        # Remove from user tracking
        if info.user_id and info.user_id in self._user_connections:
            self._user_connections[info.user_id].discard(websocket)
            if not self._user_connections[info.user_id]:
                del self._user_connections[info.user_id]
        
        # Remove from channel subscriptions
        for channel in info.subscriptions:
            self._channel_subscribers[channel].discard(websocket)
        
        logger.info(
            f"📡 WebSocket disconnected from {info.client_ip} "
            f"(total: {len(self._connections)}, "
            f"duration: {(datetime.now(timezone.utc) - info.metrics.connected_at).seconds}s)"
        )
        
        # Trigger callbacks
        for callback in self._on_disconnect_callbacks:
            try:
                asyncio.create_task(callback(websocket, info))
            except Exception as e:
                logger.error(f"Disconnect callback error: {e}")
    
    async def authenticate(self, websocket: WebSocket, user_id: str) -> bool:
        """Authenticate a connection and associate with user."""
        info = self._connections.get(websocket)
        if not info:
            return False
        
        # Check user connection limit
        current_user_connections = len(self._user_connections.get(user_id, set()))
        if current_user_connections >= self.max_connections_per_user:
            await self.send_json(websocket, {
                "type": "error",
                "code": "USER_LIMIT_EXCEEDED",
                "message": f"Maximum {self.max_connections_per_user} connections per user"
            })
            return False
        
        info.user_id = user_id
        info.state = ConnectionState.AUTHENTICATED
        self._user_connections[user_id].add(websocket)
        
        logger.info(f"✅ WebSocket authenticated for user {user_id}")
        return True
    
    # ============================================
    # MESSAGE HANDLING
    # ============================================
    
    async def send_json(
        self,
        websocket: WebSocket,
        data: Dict[str, Any]
    ) -> bool:
        """Send JSON message to a connection with metrics tracking."""
        info = self._connections.get(websocket)
        if not info:
            return False
        
        try:
            message = json.dumps(data)
            message_bytes = len(message.encode())
            
            await websocket.send_text(message)
            
            info.metrics.messages_sent += 1
            info.metrics.bytes_sent += message_bytes
            info.metrics.last_activity = datetime.now(timezone.utc)
            self._total_messages_sent += 1
            
            return True
        except Exception as e:
            info.metrics.errors += 1
            logger.debug(f"Send error: {e}")
            return False
    
    async def receive_json(
        self,
        websocket: WebSocket,
        timeout: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Receive JSON message with rate limiting and size validation."""
        info = self._connections.get(websocket)
        if not info:
            return None
        
        # Check rate limit
        if not self._rate_limiter.consume(info):
            await self.send_json(websocket, {
                "type": "error",
                "code": "RATE_LIMITED",
                "message": "Too many messages. Please slow down."
            })
            return None
        
        try:
            if timeout:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=timeout
                )
            else:
                data = await websocket.receive_text()
            
            # Size validation
            if len(data) > self.MAX_MESSAGE_SIZE:
                await self.send_json(websocket, {
                    "type": "error",
                    "code": "MESSAGE_TOO_LARGE",
                    "message": f"Message exceeds {self.MAX_MESSAGE_SIZE} bytes"
                })
                return None
            
            message = json.loads(data)
            
            info.metrics.messages_received += 1
            info.metrics.bytes_received += len(data.encode())
            info.metrics.last_activity = datetime.now(timezone.utc)
            self._total_messages_received += 1
            
            # Trigger callbacks
            for callback in self._on_message_callbacks:
                try:
                    await callback(websocket, message)
                except Exception as e:
                    logger.error(f"Message callback error: {e}")
            
            return message
            
        except asyncio.TimeoutError:
            return None
        except json.JSONDecodeError:
            logger.debug("Invalid JSON received")
            return None
        except WebSocketDisconnect:
            self.disconnect(websocket)
            raise
        except Exception as e:
            info.metrics.errors += 1
            logger.warning(f"Receive error: {e}")
            return None
    
    # ============================================
    # CHANNEL SUBSCRIPTIONS
    # ============================================
    
    def subscribe(self, websocket: WebSocket, channel: str) -> bool:
        """Subscribe connection to a channel."""
        info = self._connections.get(websocket)
        if not info:
            return False
        
        info.subscriptions.add(channel)
        self._channel_subscribers[channel].add(websocket)
        logger.debug(f"📡 Subscribed to {channel}")
        return True
    
    def unsubscribe(self, websocket: WebSocket, channel: str) -> bool:
        """Unsubscribe connection from a channel."""
        info = self._connections.get(websocket)
        if not info:
            return False
        
        info.subscriptions.discard(channel)
        self._channel_subscribers[channel].discard(websocket)
        logger.debug(f"📡 Unsubscribed from {channel}")
        return True
    
    async def broadcast_to_channel(
        self,
        channel: str,
        data: Dict[str, Any],
        exclude: Optional[Set[WebSocket]] = None
    ) -> int:
        """Broadcast message to all channel subscribers."""
        subscribers = self._channel_subscribers.get(channel, set())
        if not subscribers:
            return 0
        
        exclude = exclude or set()
        sent_count = 0
        failed = set()
        
        for websocket in subscribers:
            if websocket in exclude:
                continue
            
            success = await self.send_json(websocket, data)
            if success:
                sent_count += 1
            else:
                failed.add(websocket)
        
        # Clean up failed connections
        for ws in failed:
            self.disconnect(ws)
        
        return sent_count
    
    async def broadcast_all(
        self,
        data: Dict[str, Any],
        only_authenticated: bool = False
    ) -> int:
        """Broadcast message to all connections."""
        sent_count = 0
        failed = set()
        
        for websocket, info in list(self._connections.items()):
            if only_authenticated and info.state != ConnectionState.AUTHENTICATED:
                continue
            
            success = await self.send_json(websocket, data)
            if success:
                sent_count += 1
            else:
                failed.add(websocket)
        
        for ws in failed:
            self.disconnect(ws)
        
        return sent_count
    
    async def broadcast_to_user(
        self,
        user_id: str,
        data: Dict[str, Any]
    ) -> int:
        """Broadcast message to all connections for a specific user."""
        connections = self._user_connections.get(user_id, set())
        if not connections:
            return 0
        
        sent_count = 0
        for websocket in list(connections):
            if await self.send_json(websocket, data):
                sent_count += 1
        
        return sent_count
    
    # ============================================
    # HEALTH MONITORING
    # ============================================
    
    async def start_health_check(self) -> None:
        """Start background health check task."""
        if self._health_check_task:
            return
        
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("🏥 WebSocket health check started")
    
    async def stop_health_check(self) -> None:
        """Stop health check task."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
    
    async def _health_check_loop(self) -> None:
        """Background loop to check connection health."""
        while not self._is_shutting_down:
            try:
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
                await self._cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _cleanup_stale_connections(self) -> None:
        """Remove connections that have been idle too long."""
        now = datetime.now(timezone.utc)
        timeout_threshold = now - timedelta(seconds=self.connection_timeout)
        
        stale_connections = []
        for websocket, info in list(self._connections.items()):
            if info.metrics.last_activity < timeout_threshold:
                stale_connections.append(websocket)
        
        for websocket in stale_connections:
            logger.info(f"🧹 Closing stale connection")
            try:
                await websocket.close(code=4000, reason="Connection timeout")
            except Exception:
                pass
            self.disconnect(websocket)
        
        if stale_connections:
            logger.info(f"🧹 Cleaned up {len(stale_connections)} stale connections")
    
    # ============================================
    # GRACEFUL SHUTDOWN
    # ============================================
    
    async def graceful_shutdown(self, drain_timeout: int = 10) -> None:
        """
        Gracefully shutdown all connections.
        
        1. Stop accepting new connections
        2. Notify all clients
        3. Wait for connections to close
        4. Force close remaining connections
        """
        self._is_shutting_down = True
        
        logger.info("🛑 Initiating graceful WebSocket shutdown...")
        
        # Stop health check
        await self.stop_health_check()
        
        # Notify all clients
        shutdown_message = {
            "type": "system",
            "action": "shutdown",
            "message": "Server shutting down. Please reconnect shortly.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await self.broadcast_all(shutdown_message)
        
        # Wait for connections to close naturally
        start_time = time.time()
        while self._connections and (time.time() - start_time) < drain_timeout:
            await asyncio.sleep(0.5)
            logger.debug(f"⏳ Waiting for {len(self._connections)} connections to close...")
        
        # Force close remaining connections
        remaining = len(self._connections)
        if remaining > 0:
            logger.info(f"🔌 Force closing {remaining} remaining connections")
            
            for websocket in list(self._connections.keys()):
                try:
                    await websocket.close(code=1001, reason="Server shutdown")
                except Exception:
                    pass
                self.disconnect(websocket)
        
        logger.info("✅ WebSocket graceful shutdown complete")
    
    # ============================================
    # METRICS & STATUS
    # ============================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive WebSocket metrics."""
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        
        # Connection state distribution
        state_counts = defaultdict(int)
        for info in self._connections.values():
            state_counts[info.state.value] += 1
        
        # Calculate connection statistics
        total_bytes_sent = sum(
            info.metrics.bytes_sent for info in self._connections.values()
        )
        total_bytes_received = sum(
            info.metrics.bytes_received for info in self._connections.values()
        )
        
        return {
            "connections": {
                "current": len(self._connections),
                "total_ever": self._total_connections_ever,
                "by_state": dict(state_counts),
                "unique_ips": len(self._ip_connections),
                "unique_users": len(self._user_connections),
            },
            "messages": {
                "sent": self._total_messages_sent,
                "received": self._total_messages_received,
                "bytes_sent": total_bytes_sent,
                "bytes_received": total_bytes_received,
            },
            "channels": {
                channel: len(subscribers)
                for channel, subscribers in self._channel_subscribers.items()
            },
            "uptime_seconds": uptime,
            "is_shutting_down": self._is_shutting_down,
            "limits": {
                "max_per_ip": self.max_connections_per_ip,
                "max_per_user": self.max_connections_per_user,
                "max_total": self.max_total_connections,
            }
        }
    
    def get_connection_info(self, websocket: WebSocket) -> Optional[Dict[str, Any]]:
        """Get information about a specific connection."""
        info = self._connections.get(websocket)
        if not info:
            return None
        
        return {
            "client_ip": info.client_ip,
            "user_id": info.user_id,
            "state": info.state.value,
            "subscriptions": list(info.subscriptions),
            "connected_at": info.metrics.connected_at.isoformat(),
            "last_activity": info.metrics.last_activity.isoformat(),
            "messages_sent": info.metrics.messages_sent,
            "messages_received": info.metrics.messages_received,
            "errors": info.metrics.errors,
        }
    
    # ============================================
    # HELPER METHODS
    # ============================================
    
    def _get_client_ip(self, websocket: WebSocket) -> str:
        """Extract client IP from WebSocket connection."""
        # Check for forwarded headers (behind proxy/load balancer)
        headers = dict(websocket.headers)
        
        forwarded_for = headers.get("x-forwarded-for", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = headers.get("x-real-ip", "")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if websocket.client:
            return websocket.client.host
        
        return "unknown"
    
    def _check_connection_limits(self, client_ip: str) -> bool:
        """Check if connection should be allowed based on limits."""
        # Check total connections
        if len(self._connections) >= self.max_total_connections:
            logger.warning("⚠️ Total connection limit reached")
            return False
        
        # Check per-IP connections
        ip_count = len(self._ip_connections.get(client_ip, set()))
        if ip_count >= self.max_connections_per_ip:
            logger.warning(f"⚠️ Per-IP limit reached for {client_ip}")
            return False
        
        return True
    
    @property
    def connection_count(self) -> int:
        """Get current connection count."""
        return len(self._connections)
    
    @property
    def authenticated_count(self) -> int:
        """Get count of authenticated connections."""
        return sum(
            1 for info in self._connections.values()
            if info.state == ConnectionState.AUTHENTICATED
        )
    
    # ============================================
    # EVENT CALLBACKS
    # ============================================
    
    def on_connect(self, callback: Callable) -> None:
        """Register callback for new connections."""
        self._on_connect_callbacks.append(callback)
    
    def on_disconnect(self, callback: Callable) -> None:
        """Register callback for disconnections."""
        self._on_disconnect_callbacks.append(callback)
    
    def on_message(self, callback: Callable) -> None:
        """Register callback for received messages."""
        self._on_message_callbacks.append(callback)


# Global instance for the application
enterprise_ws_manager = EnterpriseWebSocketManager()
