"""
Enterprise WebSocket Tests
Comprehensive test suite for WebSocket functionality.

Tests cover:
- Connection management (accept, disconnect, limits)
- Rate limiting
- Message handling
- Channel subscriptions
- Broadcasting
- Health monitoring
- Graceful shutdown
- Metrics collection
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

# Import the WebSocket manager
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.websocket_manager import (
    EnterpriseWebSocketManager,
    ConnectionState,
    ConnectionInfo,
    ConnectionMetrics,
    RateLimiter,
)


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def ws_manager():
    """Create a fresh WebSocket manager for each test."""
    return EnterpriseWebSocketManager(
        max_connections_per_ip=5,
        max_connections_per_user=3,
        max_total_connections=100,
        message_rate_limit=10.0,
        connection_timeout=60
    )


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.headers = {}
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    return ws


@pytest.fixture
def mock_websockets(mock_websocket):
    """Create multiple mock WebSockets."""
    websockets = []
    for i in range(10):
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock()
        ws.headers = {"x-forwarded-for": f"192.168.1.{i}"}
        ws.client = MagicMock()
        ws.client.host = f"192.168.1.{i}"
        websockets.append(ws)
    return websockets


# ============================================
# CONNECTION MANAGEMENT TESTS
# ============================================

class TestConnectionManagement:
    """Tests for connection lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_accept_connection_success(self, ws_manager, mock_websocket):
        """Test successful connection acceptance."""
        accepted = await ws_manager.accept_connection(mock_websocket)
        
        assert accepted is True
        mock_websocket.accept.assert_called_once()
        assert ws_manager.connection_count == 1
        assert mock_websocket in ws_manager._connections
    
    @pytest.mark.asyncio
    async def test_accept_connection_sends_welcome(self, ws_manager, mock_websocket):
        """Test that welcome message is sent on connection."""
        await ws_manager.accept_connection(mock_websocket)
        
        # Verify welcome message was sent
        mock_websocket.send_text.assert_called()
        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == "connection"
        assert message["status"] == "connected"
        assert "timestamp" in message
    
    @pytest.mark.asyncio
    async def test_disconnect_cleanup(self, ws_manager, mock_websocket):
        """Test that disconnect properly cleans up resources."""
        await ws_manager.accept_connection(mock_websocket)
        assert ws_manager.connection_count == 1
        
        ws_manager.disconnect(mock_websocket)
        
        assert ws_manager.connection_count == 0
        assert mock_websocket not in ws_manager._connections
    
    @pytest.mark.asyncio
    async def test_per_ip_connection_limit(self, ws_manager):
        """Test that per-IP connection limits are enforced."""
        connections = []
        
        # Create websockets with same IP
        for i in range(7):  # Try to exceed limit of 5
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.close = AsyncMock()
            ws.send_text = AsyncMock()
            ws.headers = {}
            ws.client = MagicMock()
            ws.client.host = "192.168.1.100"  # Same IP
            connections.append(ws)
        
        # First 5 should succeed
        for i in range(5):
            result = await ws_manager.accept_connection(connections[i])
            assert result is True
        
        # 6th and 7th should fail
        result = await ws_manager.accept_connection(connections[5])
        assert result is False
        connections[5].close.assert_called()
        
        result = await ws_manager.accept_connection(connections[6])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_total_connection_limit(self, ws_manager):
        """Test that total connection limit is enforced."""
        # Set a low limit for testing
        ws_manager.max_total_connections = 3
        
        websockets = []
        for i in range(5):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.close = AsyncMock()
            ws.send_text = AsyncMock()
            ws.headers = {}
            ws.client = MagicMock()
            ws.client.host = f"192.168.1.{i}"  # Different IPs
            websockets.append(ws)
        
        # First 3 should succeed
        for i in range(3):
            result = await ws_manager.accept_connection(websockets[i])
            assert result is True
        
        # 4th should fail
        result = await ws_manager.accept_connection(websockets[3])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_connection_rejected_during_shutdown(self, ws_manager, mock_websocket):
        """Test that connections are rejected during shutdown."""
        ws_manager._is_shutting_down = True
        
        result = await ws_manager.accept_connection(mock_websocket)
        
        assert result is False
        mock_websocket.close.assert_called()
    
    @pytest.mark.asyncio
    async def test_authenticate_connection(self, ws_manager, mock_websocket):
        """Test user authentication."""
        await ws_manager.accept_connection(mock_websocket)
        
        result = await ws_manager.authenticate(mock_websocket, "user123")
        
        assert result is True
        info = ws_manager._connections[mock_websocket]
        assert info.user_id == "user123"
        assert info.state == ConnectionState.AUTHENTICATED
        assert mock_websocket in ws_manager._user_connections["user123"]
    
    @pytest.mark.asyncio
    async def test_per_user_connection_limit(self, ws_manager):
        """Test that per-user connection limits are enforced."""
        # Create multiple connections for same user
        websockets = []
        for i in range(5):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.close = AsyncMock()
            ws.send_text = AsyncMock()
            ws.headers = {}
            ws.client = MagicMock()
            ws.client.host = f"192.168.1.{i}"  # Different IPs
            websockets.append(ws)
        
        # Accept and authenticate
        for i in range(3):  # Limit is 3
            await ws_manager.accept_connection(websockets[i])
            result = await ws_manager.authenticate(websockets[i], "user123")
            assert result is True
        
        # 4th should fail authentication
        await ws_manager.accept_connection(websockets[3])
        result = await ws_manager.authenticate(websockets[3], "user123")
        assert result is False


# ============================================
# RATE LIMITING TESTS
# ============================================

class TestRateLimiting:
    """Tests for message rate limiting."""
    
    def test_rate_limiter_allows_messages(self):
        """Test that rate limiter allows messages within limit."""
        limiter = RateLimiter(tokens_per_second=10.0, max_tokens=20.0)
        info = ConnectionInfo(
            websocket=MagicMock(),
            client_ip="127.0.0.1"
        )
        
        # Should allow first 10 messages
        for _ in range(10):
            assert limiter.consume(info) is True
    
    def test_rate_limiter_blocks_excess(self):
        """Test that rate limiter blocks excess messages."""
        limiter = RateLimiter(tokens_per_second=5.0, max_tokens=5.0)
        info = ConnectionInfo(
            websocket=MagicMock(),
            client_ip="127.0.0.1"
        )
        info.rate_limit_tokens = 5.0
        
        # Consume all tokens
        for _ in range(5):
            limiter.consume(info)
        
        # Next message should be blocked
        assert limiter.consume(info) is False
    
    def test_rate_limiter_refills(self):
        """Test that rate limiter refills over time."""
        import time
        
        limiter = RateLimiter(tokens_per_second=10.0, max_tokens=10.0)
        info = ConnectionInfo(
            websocket=MagicMock(),
            client_ip="127.0.0.1"
        )
        info.rate_limit_tokens = 0  # Empty
        info.last_rate_refill = time.time() - 1  # 1 second ago
        
        # After 1 second, should have 10 tokens
        result = limiter.consume(info)
        assert result is True
        assert info.rate_limit_tokens >= 9.0  # Had 10, consumed 1


# ============================================
# MESSAGE HANDLING TESTS
# ============================================

class TestMessageHandling:
    """Tests for message sending and receiving."""
    
    @pytest.mark.asyncio
    async def test_send_json_success(self, ws_manager, mock_websocket):
        """Test successful JSON message sending."""
        await ws_manager.accept_connection(mock_websocket)
        
        result = await ws_manager.send_json(mock_websocket, {"type": "test"})
        
        assert result is True
        mock_websocket.send_text.assert_called()
        info = ws_manager._connections[mock_websocket]
        assert info.metrics.messages_sent >= 1
    
    @pytest.mark.asyncio
    async def test_send_json_tracks_bytes(self, ws_manager, mock_websocket):
        """Test that bytes sent are tracked."""
        await ws_manager.accept_connection(mock_websocket)
        
        data = {"type": "test", "data": "x" * 100}
        await ws_manager.send_json(mock_websocket, data)
        
        info = ws_manager._connections[mock_websocket]
        assert info.metrics.bytes_sent > 100
    
    @pytest.mark.asyncio
    async def test_receive_json_rate_limited(self, ws_manager, mock_websocket):
        """Test that receive is rate limited."""
        await ws_manager.accept_connection(mock_websocket)
        
        # Exhaust rate limit
        info = ws_manager._connections[mock_websocket]
        info.rate_limit_tokens = 0
        
        mock_websocket.receive_text = AsyncMock(return_value='{"type": "test"}')
        
        result = await ws_manager.receive_json(mock_websocket)
        
        # Should return None due to rate limit
        assert result is None
        # Should have sent error message
        assert mock_websocket.send_text.call_count >= 1


# ============================================
# CHANNEL SUBSCRIPTION TESTS
# ============================================

class TestChannelSubscriptions:
    """Tests for channel subscription functionality."""
    
    @pytest.mark.asyncio
    async def test_subscribe_to_channel(self, ws_manager, mock_websocket):
        """Test subscribing to a channel."""
        await ws_manager.accept_connection(mock_websocket)
        
        result = ws_manager.subscribe(mock_websocket, "prices")
        
        assert result is True
        info = ws_manager._connections[mock_websocket]
        assert "prices" in info.subscriptions
        assert mock_websocket in ws_manager._channel_subscribers["prices"]
    
    @pytest.mark.asyncio
    async def test_unsubscribe_from_channel(self, ws_manager, mock_websocket):
        """Test unsubscribing from a channel."""
        await ws_manager.accept_connection(mock_websocket)
        ws_manager.subscribe(mock_websocket, "prices")
        
        result = ws_manager.unsubscribe(mock_websocket, "prices")
        
        assert result is True
        info = ws_manager._connections[mock_websocket]
        assert "prices" not in info.subscriptions
    
    @pytest.mark.asyncio
    async def test_broadcast_to_channel(self, ws_manager, mock_websockets):
        """Test broadcasting to channel subscribers."""
        # Connect and subscribe some websockets
        for i in range(5):
            await ws_manager.accept_connection(mock_websockets[i])
            if i < 3:  # Only first 3 subscribe
                ws_manager.subscribe(mock_websockets[i], "prices")
        
        # Broadcast
        count = await ws_manager.broadcast_to_channel(
            "prices",
            {"type": "price_update", "data": {}}
        )
        
        assert count == 3
        # First 3 should have received message
        for i in range(3):
            assert mock_websockets[i].send_text.call_count >= 2  # Welcome + broadcast
    
    @pytest.mark.asyncio
    async def test_broadcast_excludes_specified(self, ws_manager, mock_websockets):
        """Test that broadcast excludes specified connections."""
        for i in range(3):
            await ws_manager.accept_connection(mock_websockets[i])
            ws_manager.subscribe(mock_websockets[i], "prices")
        
        # Broadcast excluding first connection
        count = await ws_manager.broadcast_to_channel(
            "prices",
            {"type": "test"},
            exclude={mock_websockets[0]}
        )
        
        assert count == 2


# ============================================
# BROADCASTING TESTS
# ============================================

class TestBroadcasting:
    """Tests for broadcast functionality."""
    
    @pytest.mark.asyncio
    async def test_broadcast_all(self, ws_manager, mock_websockets):
        """Test broadcasting to all connections."""
        for i in range(5):
            await ws_manager.accept_connection(mock_websockets[i])
        
        count = await ws_manager.broadcast_all({"type": "system"})
        
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_broadcast_only_authenticated(self, ws_manager, mock_websockets):
        """Test broadcasting to only authenticated connections."""
        for i in range(5):
            await ws_manager.accept_connection(mock_websockets[i])
            if i < 2:  # Only first 2 authenticated
                await ws_manager.authenticate(mock_websockets[i], f"user{i}")
        
        count = await ws_manager.broadcast_all(
            {"type": "private"},
            only_authenticated=True
        )
        
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_broadcast_to_user(self, ws_manager, mock_websockets):
        """Test broadcasting to specific user."""
        # User with multiple connections
        for i in range(3):
            mock_websockets[i].client.host = f"192.168.1.{i}"
            await ws_manager.accept_connection(mock_websockets[i])
            await ws_manager.authenticate(mock_websockets[i], "user123")
        
        # Another user
        mock_websockets[3].client.host = "192.168.1.3"
        await ws_manager.accept_connection(mock_websockets[3])
        await ws_manager.authenticate(mock_websockets[3], "user456")
        
        count = await ws_manager.broadcast_to_user(
            "user123",
            {"type": "notification"}
        )
        
        assert count == 3


# ============================================
# METRICS TESTS
# ============================================

class TestMetrics:
    """Tests for metrics collection."""
    
    @pytest.mark.asyncio
    async def test_get_metrics(self, ws_manager, mock_websockets):
        """Test metrics collection."""
        for i in range(3):
            await ws_manager.accept_connection(mock_websockets[i])
        
        metrics = ws_manager.get_metrics()
        
        assert metrics["connections"]["current"] == 3
        assert metrics["connections"]["total_ever"] == 3
        assert "messages" in metrics
        assert "uptime_seconds" in metrics
    
    @pytest.mark.asyncio
    async def test_connection_info(self, ws_manager, mock_websocket):
        """Test getting individual connection info."""
        await ws_manager.accept_connection(mock_websocket)
        await ws_manager.authenticate(mock_websocket, "user123")
        ws_manager.subscribe(mock_websocket, "prices")
        
        info = ws_manager.get_connection_info(mock_websocket)
        
        assert info is not None
        assert info["user_id"] == "user123"
        assert info["state"] == "authenticated"
        assert "prices" in info["subscriptions"]


# ============================================
# GRACEFUL SHUTDOWN TESTS
# ============================================

class TestGracefulShutdown:
    """Tests for graceful shutdown functionality."""
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_notifies_clients(self, ws_manager, mock_websockets):
        """Test that shutdown notifies all clients."""
        for i in range(3):
            await ws_manager.accept_connection(mock_websockets[i])
        
        # Start shutdown (with short timeout)
        await ws_manager.graceful_shutdown(drain_timeout=1)
        
        # All connections should have received shutdown message
        for ws in mock_websockets[:3]:
            sent_messages = [
                json.loads(call[0][0])
                for call in ws.send_text.call_args_list
            ]
            shutdown_messages = [m for m in sent_messages if m.get("type") == "system"]
            assert len(shutdown_messages) >= 1
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_force_closes(self, ws_manager, mock_websocket):
        """Test that shutdown force closes remaining connections."""
        await ws_manager.accept_connection(mock_websocket)
        
        await ws_manager.graceful_shutdown(drain_timeout=1)
        
        # Connection should be closed
        mock_websocket.close.assert_called()
        assert ws_manager.connection_count == 0


# ============================================
# CLIENT IP EXTRACTION TESTS
# ============================================

class TestClientIpExtraction:
    """Tests for client IP extraction from headers."""
    
    @pytest.mark.asyncio
    async def test_extract_from_x_forwarded_for(self, ws_manager):
        """Test extracting IP from X-Forwarded-For header."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        ws.headers = {"x-forwarded-for": "10.0.0.1, 192.168.1.1"}
        ws.client = MagicMock()
        ws.client.host = "127.0.0.1"
        
        await ws_manager.accept_connection(ws)
        
        info = ws_manager._connections[ws]
        assert info.client_ip == "10.0.0.1"
    
    @pytest.mark.asyncio
    async def test_extract_from_x_real_ip(self, ws_manager):
        """Test extracting IP from X-Real-IP header."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_text = AsyncMock()
        ws.headers = {"x-real-ip": "10.0.0.2"}
        ws.client = MagicMock()
        ws.client.host = "127.0.0.1"
        
        await ws_manager.accept_connection(ws)
        
        info = ws_manager._connections[ws]
        assert info.client_ip == "10.0.0.2"
    
    @pytest.mark.asyncio
    async def test_fallback_to_direct_ip(self, ws_manager, mock_websocket):
        """Test fallback to direct connection IP."""
        mock_websocket.headers = {}
        mock_websocket.client.host = "203.0.113.1"
        
        await ws_manager.accept_connection(mock_websocket)
        
        info = ws_manager._connections[mock_websocket]
        assert info.client_ip == "203.0.113.1"


# ============================================
# CALLBACK TESTS
# ============================================

class TestCallbacks:
    """Tests for event callbacks."""
    
    @pytest.mark.asyncio
    async def test_on_connect_callback(self, ws_manager, mock_websocket):
        """Test on_connect callback is triggered."""
        callback_called = False
        callback_data = {}
        
        async def on_connect(ws, info):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = {"ws": ws, "info": info}
        
        ws_manager.on_connect(on_connect)
        await ws_manager.accept_connection(mock_websocket)
        
        assert callback_called is True
        assert callback_data["ws"] == mock_websocket
    
    @pytest.mark.asyncio
    async def test_on_disconnect_callback(self, ws_manager, mock_websocket):
        """Test on_disconnect callback is triggered."""
        callback_called = False
        
        async def on_disconnect(ws, info):
            nonlocal callback_called
            callback_called = True
        
        ws_manager.on_disconnect(on_disconnect)
        await ws_manager.accept_connection(mock_websocket)
        ws_manager.disconnect(mock_websocket)
        
        # Wait for async callback
        await asyncio.sleep(0.1)
        
        assert callback_called is True


# ============================================
# HEALTH CHECK TESTS
# ============================================

class TestHealthCheck:
    """Tests for health check functionality."""
    
    @pytest.mark.asyncio
    async def test_start_health_check(self, ws_manager):
        """Test starting health check task."""
        await ws_manager.start_health_check()
        
        assert ws_manager._health_check_task is not None
        
        # Cleanup
        await ws_manager.stop_health_check()
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_connections(self, ws_manager, mock_websocket):
        """Test that stale connections are cleaned up."""
        await ws_manager.accept_connection(mock_websocket)
        
        # Make connection stale
        info = ws_manager._connections[mock_websocket]
        info.metrics.last_activity = datetime.now(timezone.utc) - timedelta(seconds=400)
        
        # Run cleanup
        await ws_manager._cleanup_stale_connections()
        
        # Connection should be removed
        mock_websocket.close.assert_called()
        assert ws_manager.connection_count == 0


# ============================================
# RUN TESTS
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
