"""
Socket.IO Server Integration for Real-time Communication
Provides WebSocket with auto-reconnection, heartbeats, and room-based broadcasting.

Enterprise Features:
- CORS configuration matching backend settings
- JWT token validation for authenticated connections
- Room-based broadcasting (user-specific, global)
- Connection state tracking with heartbeat
"""
import logging
import socketio
import asyncio
from typing import Dict, Set, Optional, List
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


class SocketIOManager:
    """
    Socket.IO manager for real-time communication.
    Features:
    - Auto-reconnection with exponential backoff
    - Heartbeat/ping-pong for connection health
    - Room-based broadcasting (user-specific, global)
    - Connection state tracking
    """
    
    def __init__(self):
        # Get CORS origins from settings (environment-aware)
        # In development, allow all origins for easier testing
        if settings.environment == "development":
            cors_origins = "*"
            logger.warning("⚠️ Socket.IO CORS set to wildcard - development mode")
        else:
            cors_origins = settings.get_socketio_cors_origins()
            logger.info(f"🔒 Socket.IO CORS configured for {len(cors_origins)} origin(s)")
        
        # Create Socket.IO server with CORS support
        # IMPORTANT: For credential-based auth, cannot use wildcard in production
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins=cors_origins,
            cors_credentials=True if cors_origins != "*" else False,  # No credentials with wildcard
            logger=settings.environment == "development",
            engineio_logger=False,
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1000000,
            # Transport fallback: WebSocket first, then polling
            # This ensures compatibility with restrictive network environments
            transports=['websocket', 'polling'],
        )
        
        # Track connections: {sid: {user_id, connected_at, last_ping}}
        self.connections: Dict[str, Dict] = {}
        
        # Track user sessions: {user_id: [sid1, sid2, ...]}
        self.user_sessions: Dict[str, Set[str]] = {}
        
        # Setup event handlers
        self._setup_handlers()
        
        logger.info("🔌 Socket.IO server initialized")
    
    def _setup_handlers(self):
        """Setup Socket.IO event handlers."""
        
        @self.sio.event
        async def connect(sid, environ):
            """Handle client connection."""
            self.connections[sid] = {
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_ping": datetime.now(timezone.utc).isoformat(),
                "user_id": None
            }
            
            logger.info(f"🟢 Client connected: {sid}")
            
            # Send welcome message
            await self.sio.emit('connected', {
                "message": "Connected to CryptoVault WebSocket",
                "sid": sid,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, room=sid)
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection."""
            if sid in self.connections:
                user_id = self.connections[sid].get("user_id")
                
                # Remove from user sessions
                if user_id and user_id in self.user_sessions:
                    self.user_sessions[user_id].discard(sid)
                    if not self.user_sessions[user_id]:
                        del self.user_sessions[user_id]
                
                del self.connections[sid]
                logger.info(f"🔴 Client disconnected: {sid} (user: {user_id})")
        
        @self.sio.event
        async def authenticate(sid, data):
            """
            Authenticate user and join user-specific room.
            Validates JWT token before allowing authenticated access.
            """
            try:
                from auth import decode_token
                
                user_id = data.get("user_id")
                token = data.get("token")
                
                if not user_id or not token:
                    await self.sio.emit('auth_error', {
                        "error": "Missing credentials",
                        "code": "MISSING_CREDENTIALS"
                    }, room=sid)
                    return
                
                # Validate JWT token
                payload = decode_token(token, expected_type="access")
                
                if not payload:
                    logger.warning(f"❌ Invalid token for Socket.IO auth (sid: {sid})")
                    await self.sio.emit('auth_error', {
                        "error": "Invalid or expired token",
                        "code": "INVALID_TOKEN"
                    }, room=sid)
                    return
                
                # Verify user_id matches token subject
                token_user_id = payload.get("sub")
                if token_user_id != user_id:
                    logger.warning(f"❌ User ID mismatch in Socket.IO auth (sid: {sid})")
                    await self.sio.emit('auth_error', {
                        "error": "User ID mismatch",
                        "code": "USER_MISMATCH"
                    }, room=sid)
                    return
                
                # Token is valid - authenticate the connection
                self.connections[sid]["user_id"] = user_id
                self.connections[sid]["authenticated_at"] = datetime.now(timezone.utc).isoformat()
                
                # Add to user sessions
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = set()
                self.user_sessions[user_id].add(sid)
                
                # Join user-specific room
                await self.sio.enter_room(sid, f"user:{user_id}")
                
                logger.info(f"✅ User authenticated via Socket.IO: {user_id} (sid: {sid})")
                
                await self.sio.emit('authenticated', {
                    "success": True,
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, room=sid)
            
            except Exception as e:
                logger.error(f"Socket.IO authentication error: {e}")
                await self.sio.emit('auth_error', {
                    "error": "Authentication failed",
                    "code": "AUTH_ERROR"
                }, room=sid)
        
        @self.sio.event
        async def subscribe(sid, data):
            """Subscribe to specific channels (prices, notifications, etc.)."""
            try:
                channels = data.get("channels", [])
                
                for channel in channels:
                    await self.sio.enter_room(sid, f"channel:{channel}")
                    logger.debug(f"📡 {sid} subscribed to {channel}")
                
                await self.sio.emit('subscribed', {
                    "channels": channels
                }, room=sid)
            
            except Exception as e:
                logger.error(f"Subscribe error: {e}")
        
        @self.sio.event
        async def unsubscribe(sid, data):
            """Unsubscribe from channels."""
            try:
                channels = data.get("channels", [])
                
                for channel in channels:
                    await self.sio.leave_room(sid, f"channel:{channel}")
                    logger.debug(f"📡 {sid} unsubscribed from {channel}")
                
                await self.sio.emit('unsubscribed', {
                    "channels": channels
                }, room=sid)
            
            except Exception as e:
                logger.error(f"Unsubscribe error: {e}")
        
        @self.sio.event
        async def ping(sid):
            """Handle ping for connection health check."""
            if sid in self.connections:
                self.connections[sid]["last_ping"] = datetime.now(timezone.utc).isoformat()
            
            await self.sio.emit('pong', {
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, room=sid)
    
    # ============================================
    # BROADCASTING METHODS
    # ============================================
    
    async def send_to_user(self, user_id: str, event: str, data: Dict):
        """Send message to specific user (alias for broadcast_to_user)."""
        await self.broadcast_to_user(user_id, event, data)

    async def broadcast(self, event: str, data: Dict):
        """Broadcast message to all connected clients (alias for broadcast_global)."""
        await self.broadcast_global(event, data)

    async def broadcast_to_user(self, user_id: str, event: str, data: Dict):
        """Broadcast message to specific user (all their sessions)."""
        room = f"user:{user_id}"
        await self.sio.emit(event, data, room=room)
        logger.debug(f"📤 Broadcast to user {user_id}: {event}")
    
    async def broadcast_to_channel(self, channel: str, event: str, data: Dict):
        """Broadcast message to all subscribers of a channel."""
        room = f"channel:{channel}"
        await self.sio.emit(event, data, room=room)
        logger.debug(f"📤 Broadcast to channel {channel}: {event}")
    
    async def broadcast_global(self, event: str, data: Dict):
        """Broadcast message to all connected clients."""
        await self.sio.emit(event, data)
        logger.debug(f"📤 Global broadcast: {event}")
    
    async def broadcast_price_update(self, prices: Dict[str, float]):
        """Broadcast price updates to price channel subscribers."""
        await self.broadcast_to_channel('prices', 'price_update', {
            "prices": prices,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def send_notification(self, user_id: str, notification: Dict):
        """Send notification to specific user."""
        await self.broadcast_to_user(user_id, 'notification', {
            **notification,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def send_order_update(self, user_id: str, order: Dict):
        """Send order status update to user."""
        await self.broadcast_to_user(user_id, 'order_update', {
            "order": order,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    # ============================================
    # CONNECTION MANAGEMENT
    # ============================================
    
    def get_connected_users(self) -> Set[str]:
        """Get set of currently connected user IDs."""
        return set(self.user_sessions.keys())
    
    def is_user_connected(self, user_id: str) -> bool:
        """Check if user has any active connections."""
        return user_id in self.user_sessions and len(self.user_sessions[user_id]) > 0
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.connections)
    
    def get_stats(self) -> Dict:
        """Get Socket.IO server statistics."""
        return {
            "total_connections": len(self.connections),
            "active_connections": len(self.connections),
            "authenticated_users": len(self.user_sessions),
            "connections": [
                {
                    "sid": sid,
                    "user_id": info.get("user_id"),
                    "connected_at": info.get("connected_at"),
                    "last_ping": info.get("last_ping")
                }
                for sid, info in self.connections.items()
            ]
        }


# Global Socket.IO manager instance
socketio_manager = SocketIOManager()
