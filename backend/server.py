"""
CryptoVault API Server - Production Ready
Modular, well-organized FastAPI application with comprehensive error handling,
monitoring, and production-grade features.
"""

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZIPMiddleware  # ✅ Import enabled for compression
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Optional, Set
from datetime import datetime, timezone
import logging
import asyncio
import uuid
import time
import sys
import json

# Configuration and database
from config import settings, validate_startup_environment, get_settings
import os

# Force mock database if explicitly requested via environment
# In production, we default to REAL database for data persistence
use_mock_db = os.getenv("USE_MOCK_DB", "false").lower() == "true"

if use_mock_db:
    from database_mock import DatabaseConnection
else:
    try:
        from database import DatabaseConnection
    except (ImportError, ValueError) as e:
        if settings.environment == "production":
            logger = logging.getLogger(__name__)
            logger.critical(f"💥 Failed to load production database: {e}")
            sys.exit(1)
        from database_mock import DatabaseConnection

# Routers
from routers import auth, portfolio, trading, crypto, admin, wallet, alerts, transactions, prices, websocket, transfers, users, notifications, monitoring, config, referrals, earn, contact, push
from routers.health import router as health_router
from routers.kyc_aml import router as kyc_aml_router

# Services
from services.telegram_bot import telegram_bot
from services import price_stream_service
from coincap_service import coincap_service

# Enhanced services
from socketio_server import socketio_manager
from redis_enhanced import redis_enhanced

# Phase 2 Performance Optimization Modules
from db_optimization import create_all_recommended_indexes
from performance_monitoring import performance_metrics, RequestTimer

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Dependencies
import dependencies

# ============================================
# SENTRY INTEGRATION (Error Tracking)
# ============================================

if settings.is_sentry_available():
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                LoggingIntegration(level=logging.ERROR, event_level=logging.ERROR),
            ],
            send_default_pii=False,  # Don't send PII data
            attach_stacktrace=True,
            max_breadcrumbs=50,
            before_send=lambda event, hint: event if settings.environment != 'development' else None,
        )
        print("✅ Sentry error tracking initialized")
    except Exception as e:
        print(f"⚠️ Sentry initialization failed: {e}. Continuing without error tracking.")
else:
    print("ℹ️ Sentry not configured (SENTRY_DSN not set)")

# ============================================
# LOGGING CONFIGURATION
# ============================================

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging in production."""
    
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        for field in ["request_id", "type", "method", "path", "status_code", 
                      "duration_ms", "error_type", "error_code", "user_id", "action"]:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


if settings.environment == "production":
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info("JSON logging configured for production")
else:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

# ============================================
# MIDDLEWARE CLASSES
# ============================================

class RequestIDMiddleware:
    """Add unique request ID for correlation and tracking."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request_id = str(uuid.uuid4())
        scope["request_id"] = request_id
        
        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                # Keep headers as list to preserve duplicates (like set-cookie)
                existing_headers = list(message.get("headers", []))
                existing_headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = existing_headers
            await send(message)
        
        start_time = time.time()
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": scope.get("method"),
                "path": scope.get("path"),
                "client": scope.get("client", ["UNKNOWN", 0])[0],
                "type": "request_start"
            }
        )
        
        try:
            await self.app(scope, receive, send_with_request_id)
            duration = time.time() - start_time
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "duration_ms": round(duration * 1000, 2),
                    "type": "request_complete"
                }
            )
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "duration_ms": round(duration * 1000, 2),
                    "error_type": type(exc).__name__,
                    "type": "request_error"
                },
                exc_info=True
            )
            raise


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    These are baseline security headers applied to every response.
    More comprehensive headers are added by middleware/security.py for specific routes.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                # Get existing headers as a list to preserve duplicates (like set-cookie)
                existing_headers = list(message.get("headers", []))
                existing_keys = set()
                for k, v in existing_headers:
                    # Don't track set-cookie as it can have duplicates
                    if k.lower() != b"set-cookie":
                        existing_keys.add(k.lower())
                
                # Baseline security headers - valid values per HTTP spec
                # Build CSP dynamically from config
                api_url = settings.public_api_url or "https://cryptovault-api.onrender.com"
                ws_url = api_url.replace("https://", "wss://").replace("http://", "ws://")
                coincap_api = settings.coincap_api_url.replace("/v2", "") if settings.coincap_api_url else "https://api.coincap.io"
                coincap_ws = settings.coincap_ws_url.split("?")[0] if settings.coincap_ws_url else "wss://ws.coincap.io"
                
                csp_connect_src = (
                    f"'self' {api_url} {ws_url} ws://{api_url.split('://')[1] if '://' in api_url else api_url} "
                    f"{coincap_api} {coincap_ws} wss://{coincap_ws.split('://')[1] if '://' in coincap_ws else coincap_ws} "
                    f"https://sentry.io https://*.sentry.io https://*.ingest.sentry.io "
                    f"https://vercel.live wss://vercel.live https://*.vercel.live"
                )
                
                security_headers = [
                    # HSTS - Force HTTPS for 1 year (31,536,000 seconds)
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains; preload"),
                    
                    # Prevent clickjacking
                    (b"x-frame-options", b"DENY"),
                    
                    # Prevent MIME type sniffing
                    (b"x-content-type-options", b"nosniff"),
                    
                    # Enable XSS protection
                    (b"x-xss-protection", b"1; mode=block"),
                    
                    # Referrer policy for privacy
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    
                    # Restrict browser features (crypto/fintech security)
                    (b"permissions-policy", b"geolocation=(), microphone=(), camera=(), payment=(), usb=()"),
                    
                    # Cross-Origin Isolation (Enhanced Security)
                    # COEP - Requires explicit opt-in for cross-origin resources
                    (b"cross-origin-embedder-policy", b"unsafe-none"),
                    
                    # COOP - Isolates browsing context from other origins
                    (b"cross-origin-opener-policy", b"same-origin"),
                    
                    # CORP - Controls cross-origin resource sharing
                    (b"cross-origin-resource-policy", b"cross-origin"),
                    
                    # Content Security Policy
                    (b"content-security-policy", (
                        b"default-src 'self'; "
                        b"script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com https://vercel.live https://*.vercel-scripts.com; "
                        b"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                        b"font-src 'self' https://fonts.gstatic.com data:; "
                        b"img-src 'self' data: https: blob:; "
                        b"connect-src " + csp_connect_src.encode() + b"; "
                        b"frame-ancestors 'none'; "
                        b"base-uri 'self'; "
                        b"form-action 'self'; "
                        b"upgrade-insecure-requests"
                    )),
                ]
                
                # Only add security headers that don't already exist
                for key, value in security_headers:
                    if key.lower() not in existing_keys:
                        existing_headers.append((key, value))
                
                message["headers"] = existing_headers
            
            await send(message)
        
        await self.app(scope, receive, send_with_security_headers)


class TimeoutMiddleware:
    """Add timeout protection to requests."""
    
    def __init__(self, app, timeout_seconds: int = 30):
        self.app = app
        self.timeout_seconds = timeout_seconds
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        try:
            await asyncio.wait_for(
                self.app(scope, receive, send),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout after {self.timeout_seconds} seconds")
            response = JSONResponse(
                status_code=504,
                content={"detail": "Request timeout"}
            )
            await response(scope, receive, send)


class RateLimitHeadersMiddleware:
    """Add rate limit headers to responses."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        async def send_with_rate_limit_headers(message):
            if message["type"] == "http.response.start":
                # Get existing headers as a list (preserve duplicates like set-cookie)
                existing_headers = list(message.get("headers", []))
                
                # Add rate limit headers
                rate_limit_headers = [
                    (b"x-ratelimit-limit", str(settings.rate_limit_requests_per_minute).encode()),
                    (b"x-ratelimit-policy", f"{settings.rate_limit_requests_per_minute};w=60".encode()),
                ]
                
                # Append new headers (don't convert to dict which removes duplicates)
                existing_headers.extend(rate_limit_headers)
                message["headers"] = existing_headers
            
            await send(message)
        
        await self.app(scope, receive, send_with_rate_limit_headers)


# ============================================
# RATE LIMITING
# ============================================

def get_rate_limit_key(request: Request) -> str:
    """Get rate limit key based on IP and user (from Authorization header or cookies)."""
    client_ip = get_remote_address(request)

    try:
        from auth import decode_token

        # Try Authorization header first
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if payload and payload.get("sub"):
                logger.debug(f"Rate limit key from Authorization header for user {payload.get('sub')}")
                return f"{payload.get('sub')}:{client_ip}"

        # Fall back to access_token cookie (cookie-based auth)
        access_token_cookie = request.cookies.get("access_token")
        if access_token_cookie:
            try:
                payload = decode_token(access_token_cookie)
                if payload and payload.get("sub"):
                    logger.debug(f"Rate limit key from cookie for user {payload.get('sub')}")
                    return f"{payload.get('sub')}:{client_ip}"
            except Exception as e:
                logger.debug(f"Failed to decode token from cookie: {e}")
    except Exception as e:
        logger.debug(f"Error deriving rate limit key from auth: {e}")

    # Fallback: use IP and user-agent hash
    user_agent = request.headers.get("user-agent", "")
    fallback_key = f"{client_ip}:{hash(user_agent) % 1000}"
    logger.debug(f"Rate limit key from fallback (IP+UA): {fallback_key}")
    return fallback_key


limiter = Limiter(key_func=get_rate_limit_key)

# ============================================
# LIFESPAN MANAGEMENT (STARTUP & SHUTDOWN)
# ============================================

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.
    Implements enterprise-grade initialization with health checks.
    """
    # STARTUP LOGIC
    global db_connection

    logger.info("=" * 80)
    logger.info("🚀 CRYPTOVAULT API SERVER - ENTERPRISE STARTUP")
    logger.info("=" * 80)
    logger.info(f"   Version: 1.0.0")
    logger.info(f"   Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    logger.info(f"   Host: {settings.host}")
    logger.info(f"   Port: {settings.port}")
    logger.info(f"   Environment: {settings.environment}")
    logger.info("=" * 80)

    try:
        # Run comprehensive startup health checks
        from startup import run_startup_checks
        
        can_start, health_check = await run_startup_checks()
        
        if not can_start:
            logger.critical("💥 STARTUP BLOCKED: Critical health check failures detected")
            logger.critical("Please resolve the critical issues above and restart the server")
            raise RuntimeError("Startup health check failed - server cannot start")

        # Initialize database connection with retries
        logger.info("🔌 Initializing database connection...")
        db_connection = DatabaseConnection(
            mongo_url=settings.database_url,
            db_name=settings.db_name,
            max_pool_size=settings.mongo_max_pool_size,
            min_pool_size=min(5, settings.mongo_max_pool_size),
            server_selection_timeout_ms=settings.mongo_timeout_ms
        )
        
        try:
            await db_connection.connect(max_retries=5)
            logger.info("✅ Database connection established")
        except Exception as e:
            logger.critical(f"💥 Database connection failed: {str(e)}")
            raise

        # Set global dependencies
        dependencies.set_db_connection(db_connection)
        dependencies.set_limiter(limiter)

        # Create database indexes for performance
        if db_connection.is_connected:
            try:
                logger.info("📊 Creating database indexes...")
                from database_indexes import create_indexes as create_database_indexes
                await create_database_indexes(db_connection.db)
                logger.info("✅ Database indexes created")
            except Exception as e:
                logger.warning(f"⚠️ Could not create indexes: {e}")
            
            # Phase 2: Create optimized indexes (compound indexes for query performance)
            try:
                logger.info("🚀 Creating Phase 2 optimized indexes...")
                await create_all_recommended_indexes(db_connection.db)
                logger.info("✅ Phase 2 optimized indexes created")
            except Exception as e:
                logger.warning(f"⚠️ Phase 2 index creation failed: {e}")

        # Start price stream service (non-critical)
        try:
            logger.info("📈 Starting price stream service...")
            await price_stream_service.start()
            logger.info("✅ Price stream service started")
        except Exception as e:
            logger.warning(f"⚠️ Price stream service failed to start: {e}")

        # Initialize Telegram bot notifications (non-critical)
        try:
            telegram_status = await telegram_bot.get_health_status()
            if telegram_status.get("enabled") and telegram_status.get("api_reachable"):
                logger.info(
                    "✅ Telegram bot operational (@%s)",
                    telegram_status.get("bot_username") or "unknown"
                )
                await telegram_bot.start_command_polling()
            elif telegram_status.get("feature_enabled"):
                logger.warning(
                    "⚠️ Telegram enabled but not fully operational "
                    "(configured_admin_count=%s, api_reachable=%s)",
                    telegram_status.get("configured_admin_count"),
                    telegram_status.get("api_reachable")
                )
            else:
                logger.info("ℹ️ Telegram notifications disabled")
        except Exception as e:
            logger.warning(f"⚠️ Telegram initialization error: {e}")
        
        # Initialize default admin account (non-critical)
        try:
            logger.info("👤 Ensuring admin account exists...")
            from admin_auth import create_default_admin
            await create_default_admin()
            logger.info("✅ Admin account initialized")
        except Exception as e:
            logger.warning(f"⚠️ Admin account initialization warning: {e}")

        logger.info("=" * 80)
        logger.info("✅ SERVER STARTUP COMPLETE - READY FOR REQUESTS")
        logger.info(f"   📍 Environment: {settings.environment}")
        logger.info(f"   🌍 CORS Origins: {len(settings.get_cors_origins_list())} configured")
        logger.info(f"   🔐 Security: HSTS, CSP, Rate Limiting enabled")
        logger.info("=" * 80)

    except Exception as e:
        logger.critical(f"💥 STARTUP FAILED: {str(e)}")
        logger.critical("Server cannot start. Please check the configuration and logs above.")
        raise

    yield

    # SHUTDOWN LOGIC
    logger.info("="*70)
    logger.info("🛑 Shutting down CryptoVault API Server")
    logger.info("="*70)

    await telegram_bot.stop_command_polling()
    await price_stream_service.stop()

    if db_connection:
        await db_connection.disconnect()

    logger.info("✅ Graceful shutdown complete")


# ============================================
# CREATE FASTAPI APP
# ============================================

app = FastAPI(
    title="CryptoVault API",
    version="1.0.0",
    description="Production-ready cryptocurrency trading platform with institutional-grade security",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================
# GLOBAL EXCEPTION HANDLERS (Error Standardization)
# ============================================

async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Standardize HTTP exception responses to match frontend error interface.
    Converts FastAPI HTTPException to consistent error format.
    """
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())

    # Map HTTP status codes to error codes
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }

    error_code = error_code_map.get(exc.status_code, f"HTTP_{exc.status_code}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": str(exc.detail) if exc.detail else "An error occurred",
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions and return standardized error format.
    Logs the full exception for debugging.
    """
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())

    logger.error(
        f"🔴 Unhandled exception: {str(exc)}",
        extra={
            "type": "error",
            "error_type": type(exc).__name__,
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        }
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
    )


# Register global exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# ============================================
# CORS CONFIGURATION - Enterprise Grade
# ============================================

# Get CORS origins from settings
cors_origins = settings.get_cors_origins_list()

# Log CORS configuration at startup
logger.info("=" * 60)
logger.info("🌐 CORS CONFIGURATION")
logger.info("=" * 60)

# Important: When using allow_credentials=True with cross-site auth, cannot use ["*"]
# Browsers will reject credentialed requests with wildcard CORS
# The config validation will raise an error in production if this is misconfigured
if cors_origins == ["*"]:
    if settings.environment == 'development':
        logger.warning(
            "⚠️ DEVELOPMENT: CORS_ORIGINS is set to '*' - cookie-based authentication may not work "
            "with cross-origin requests. For production, set CORS_ORIGINS to specific origins."
        )
    else:
        logger.error(
            "🛑 PRODUCTION: Wildcard CORS detected - this is a security risk! "
            "Set CORS_ORIGINS to specific frontend domains."
        )
else:
    logger.info(f"   Allowed Origins: {len(cors_origins)} configured")
    for origin in cors_origins[:3]:  # Log first 3 for brevity
        logger.info(f"     - {origin}")
    if len(cors_origins) > 3:
        logger.info(f"     ... and {len(cors_origins) - 3} more")

logger.info(f"   Credentials: Enabled (cookie-based auth)")
logger.info(f"   Max Age: 3600 seconds (preflight caching)")
logger.info("=" * 60)

# Define allowed headers explicitly for security
# These are custom headers that the frontend may send
# Note: Simple headers (Accept, Content-Type, etc.) are allowed by default
# Note: "Origin" is a forbidden header name and handled by browser automatically
ALLOWED_HEADERS = [
    "Authorization",          # Bearer tokens (JWT)
    "Content-Type",           # Required for JSON payloads
    "Accept",                 # Content negotiation
    "Accept-Language",        # Localization
    "Accept-Encoding",        # Compression negotiation
    "X-Requested-With",       # XMLHttpRequest indicator
    "X-CSRF-Token",           # CSRF protection token
    "X-Request-ID",           # Request correlation/tracing
    "Cache-Control",          # Caching directives
    "Pragma",                 # HTTP/1.0 cache control
    "If-Match",               # Conditional requests (ETags)
    "If-None-Match",          # Conditional requests (ETags)
    "X-Nowpayments-Sig",      # NOWPayments webhook signature
]

# Define exposed headers (headers the browser can access)
EXPOSED_HEADERS = [
    "X-Request-ID",           # Request correlation
    "X-RateLimit-Limit",      # Rate limit info
    "X-RateLimit-Remaining",  # Remaining requests
    "X-RateLimit-Reset",      # Reset timestamp
    "X-RateLimit-Policy",     # Rate limit policy
    "Retry-After",            # When to retry (429 responses)
    "Content-Disposition",    # File downloads
    "X-Total-Count",          # Pagination total
]

# ============================================
# CUSTOM MIDDLEWARE
# ============================================

app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitHeadersMiddleware)
app.add_middleware(TimeoutMiddleware, timeout_seconds=30)  # 30-second request timeout

# Import and add geo-blocking middleware
try:
    from middleware.geo_blocking import GeoBlockingMiddleware
    app.add_middleware(GeoBlockingMiddleware)
    logger.info("Geo-blocking middleware enabled")
except ImportError as e:
    logger.warning(f"Geo-blocking middleware not available: {e}")

# Import and add advanced security middleware from middleware/security.py
try:
    from middleware.security import (
        AdvancedRateLimiter,
        RequestValidationMiddleware,
        CSRFProtectionMiddleware
    )
    
    # Add advanced rate limiter (with burst protection and IP blocking)
    app.add_middleware(
        AdvancedRateLimiter,
        default_limit=settings.rate_limit_requests_per_minute,
        window_seconds=60,
        block_duration=15,  # Block IPs for 15 minutes on burst attack
        burst_threshold=10   # 10 requests in 1 second = burst
    )
    
    # Add request validation middleware
    app.add_middleware(RequestValidationMiddleware)
    
    # Add CSRF protection middleware
    # Enable in production, can be disabled for testing
    csrf_enabled = settings.is_production
    app.add_middleware(
        CSRFProtectionMiddleware,
        secret_key=settings.csrf_secret.get_secret_value() if settings.csrf_secret else settings.jwt_secret.get_secret_value(),
        enabled=csrf_enabled
    )
    
    logger.info("✅ Advanced security middleware enabled:")
    logger.info("   - Burst protection & IP blocking")
    logger.info("   - Input validation")
    logger.info(f"   - CSRF protection: {'ENABLED' if csrf_enabled else 'DISABLED (dev mode)'}")
except ImportError as e:
    logger.warning(f"⚠️ Advanced security middleware not available: {e}")

# ============================================
# COMPRESSION MIDDLEWARE
# ============================================

# Add GZip compression for response compression
try:
    from starlette.middleware.gzip import GZipMiddleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    logger.info("✅ GZip compression middleware enabled (min size: 1000 bytes)")
except ImportError as e:
    logger.warning(f"⚠️ GZip compression middleware not available: {e}")

# ============================================
# CORS CONFIGURATION - Enterprise Grade
# ============================================

# Apply CORS middleware LAST so it wraps everything else
# This ensures CORS headers are added even for errors or middleware responses
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=ALLOWED_HEADERS,
    expose_headers=EXPOSED_HEADERS,
    max_age=3600,
)

# ============================================
# DATABASE CONNECTION
# ============================================

db_connection: Optional[DatabaseConnection] = None

# ============================================
# API ROUTES - Version 1
# ============================================
# Mount v1 API routes (versioned) - REMOVED (archived to _legacy_archive)
# Kept as try/except for graceful degradation
try:
    pass  # v1 routes archived
    # from routers.v1 import api_v1_router
    # app.include_router(api_v1_router)
    logger.info("ℹ️ API v1 routes archived (use /api/ endpoints instead)")
except ImportError as e:
    logger.warning(f"⚠️ Could not load v1 routes: {e}")

# ============================================
# API ROUTES - Legacy (Backward Compatibility)
# ============================================
# Keep legacy routes for backward compatibility (will be deprecated)
app.include_router(auth.router, prefix="/api", tags=["legacy"])
app.include_router(portfolio.router, prefix="/api", tags=["legacy"])
app.include_router(trading.router, prefix="/api", tags=["legacy"])
app.include_router(crypto.router, prefix="/api", tags=["legacy"])
app.include_router(prices.router, prefix="/api", tags=["legacy"])
# admin router mounted separately below with correct prefix
app.include_router(wallet.router, prefix="/api", tags=["legacy"])
app.include_router(alerts.router, prefix="/api", tags=["legacy"])
app.include_router(notifications.router, prefix="/api", tags=["legacy"])
app.include_router(transactions.router, prefix="/api", tags=["legacy"])
app.include_router(transfers.router, prefix="/api", tags=["legacy"])
app.include_router(users.router, prefix="/api", tags=["legacy"])
app.include_router(config.router, prefix="/api")
app.include_router(referrals.router, prefix="/api")
app.include_router(earn.router, prefix="/api")
app.include_router(contact.router, prefix="/api")
app.include_router(push.router, prefix="/api")

# Health check endpoints (liveness + readiness probes)
app.include_router(health_router)

# KYC/AML endpoints
app.include_router(kyc_aml_router, prefix="/api", tags=["kyc"])

# Admin dashboard (custom prefix already in router)
from routers.admin import router as admin_dashboard_router
app.include_router(admin_dashboard_router)

# WebSocket (no versioning)
app.include_router(websocket.router)

# Monitoring (no versioning or auth required)
app.include_router(monitoring.router, prefix="/api")
# Removed: deep_investigation router (archived to _legacy_archive)
# app.include_router(deep_investigation.router, prefix="/api")

# Performance optimization endpoints
try:
    from routers.optimization import router as optimization_router
    app.include_router(optimization_router, prefix="/api")
    logger.info("✅ Optimization endpoints mounted at /api/optimization/")
except ImportError as e:
    logger.warning(f"⚠️ Optimization router not available: {e}")

# Version and compatibility endpoints
try:
    from routers.version import router as version_router
    app.include_router(version_router, prefix="/api")
    logger.info("✅ Version endpoints mounted at /api/version/")
except ImportError as e:
    logger.warning(f"⚠️ Version router not available: {e}")

# Fly.io deployment status - REMOVED (archived to _legacy_archive)
# Kept as try/except for graceful degradation
try:
    pass  # fly_status router archived
    # from routers.fly_status import router as fly_router
    # app.include_router(fly_router, prefix="/api")
    logger.info("ℹ️ Fly.io status endpoints archived")
except ImportError as e:
    logger.warning(f"⚠️ Fly.io status router not available: {e}")

# ============================================
# SOCKET.IO INTEGRATION
# ============================================

# Socket.IO endpoints will be available at /socket.io/
logger.info("✅ Socket.IO ready to be mounted")

# ============================================
# ROOT & HEALTH ENDPOINTS
# ============================================

@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "🚀 CryptoVault API is live and running!",
        "version": "1.0.0",
        "environment": settings.environment,
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "openapi": "/api/openapi.json",
        "health": "/health",
        "ping": "/ping",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/ping", tags=["health"])
@app.get("/api/ping", tags=["health"])
async def ping():
    """Simple ping endpoint that doesn't require database connection. For health checks and keep-alive."""
    return {
        "status": "ok",
        "message": "pong",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version
    }


@app.get("/health", tags=["health"])
@app.get("/api/health", tags=["health"])
async def health_check(request: Request):
    """
    Health check endpoint for monitoring and load balancers.
    Returns 200 if API is running, even if database is temporarily unavailable.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # Basic health - API is running
    health_status = {
        "status": "healthy",
        "api": "running",
        "environment": settings.environment,
        "version": settings.app_version,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Check database (non-critical for API health)
    try:
        if db_connection and db_connection.is_connected:
            # Try quick database ping with timeout
            try:
                await asyncio.wait_for(
                    db_connection.health_check(),
                    timeout=2.0  # Quick timeout
                )
                health_status["database"] = "connected"
            except asyncio.TimeoutError:
                health_status["database"] = "slow"
                logger.warning("Database health check timed out")
            except Exception as e:
                health_status["database"] = "error"
                logger.warning(f"Database health check error: {str(e)}")
        else:
            health_status["database"] = "initializing"
            logger.info("Database connection not yet established")
    except Exception as e:
        health_status["database"] = "unavailable"
        logger.warning(f"Database check failed: {str(e)}")

    # Return 200 OK as long as API is running
    # This allows health checks to pass during database initialization
    return health_status


@app.get("/csrf", tags=["auth"])
@app.get("/api/csrf", tags=["auth"])
async def get_csrf_token(request: Request):
    """
    Get CSRF token for form submissions.
    
    Enterprise CSRF Protection:
    - Generates cryptographically secure tokens
    - Tokens are stored in HTTP-only cookies for security
    - Also returned in response body for SPA architecture (store in memory, not localStorage)
    - Tokens rotate every hour for enhanced security
    - SameSite attribute prevents CSRF from third-party sites
    
    Usage:
    1. Call this endpoint on app initialization
    2. Store the returned token in memory (JavaScript variable)
    3. Include the token in X-CSRF-Token header for POST/PUT/PATCH/DELETE requests
    4. Token validation happens server-side for all non-idempotent requests
    """
    import secrets
    import hashlib
    from datetime import datetime
    
    # Check for existing valid token
    existing_token = request.cookies.get("csrf_token")
    existing_timestamp = request.cookies.get("csrf_timestamp")
    
    # Validate existing token age (rotate after 1 hour)
    should_rotate = True
    if existing_token and existing_timestamp:
        try:
            timestamp = float(existing_timestamp)
            age = time.time() - timestamp
            # Rotate if token is older than 1 hour (3600 seconds)
            should_rotate = age > 3600
        except (ValueError, TypeError):
            should_rotate = True
    
    if existing_token and not should_rotate:
        # Return existing valid token
        return {
            "csrf_token": existing_token,
            "expires_in": 3600 - int(time.time() - float(existing_timestamp)),
            "message": "Existing token valid"
        }
    
    # Generate new cryptographically secure CSRF token
    # Using secrets module for cryptographic randomness
    random_bytes = secrets.token_bytes(32)
    timestamp = str(time.time())
    
    # Create token with embedded timestamp for validation
    token_data = f"{random_bytes.hex()}:{timestamp}"
    csrf_token = hashlib.sha256(token_data.encode()).hexdigest()
    
    # Build response with token
    response = JSONResponse({
        "csrf_token": csrf_token,
        "expires_in": 3600,
        "message": "New token generated"
    })
    
    # Cookie settings: cross-site requires SameSite=None + Secure=True
    same_site = "none" if settings.use_cross_site_cookies else "lax"
    secure = settings.is_production or settings.use_cross_site_cookies
    
    # Set CSRF token cookie (HTTP-only for security)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,  # Prevent JavaScript access (XSS protection)
        secure=secure,   # HTTPS only in production
        samesite=same_site,
        max_age=3600,    # 1 hour expiry
        path="/"
    )
    
    # Set timestamp cookie for rotation tracking
    response.set_cookie(
        key="csrf_timestamp",
        value=timestamp,
        httponly=True,
        secure=secure,
        samesite=same_site,
        max_age=3600,
        path="/"
    )
    
    logger.info("🔐 New CSRF token generated", extra={"type": "csrf_generation"})
    
    return response


@app.get("/api/socketio/stats", tags=["monitoring"])
async def get_socketio_stats():
    """Get Socket.IO connection statistics."""
    return socketio_manager.get_stats()


# ============================================
# PHASE 2 MONITORING ENDPOINTS
# ============================================

@app.get("/api/monitor/performance", tags=["monitoring"])
async def get_performance_metrics():
    """
    Phase 2: Performance metrics endpoint for monitoring.
    Returns Core Web Vitals, API timing data, and performance summary.
    
    Response includes:
    - Core Web Vitals (LCP, FID, CLS, TTFB, FCP)
    - API endpoint performance (response times, status codes)
    - Performance status (good/poor)
    - Cache effectiveness
    - Metrics timestamp
    """
    try:
        summary = performance_metrics.get_summary()
        return {
            "status": "success",
            "data": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error retrieving performance metrics: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/monitor/circuit-breakers", tags=["monitoring"])
async def get_circuit_breaker_status():
    """
    Phase 2: Circuit breaker status endpoint.
    Returns status of all circuit breakers protecting external API calls.
    
    Pre-configured breakers:
    - BREAKER_COINCAP: CoinCap/CoinGecko API
    - BREAKER_COINMARKETCAP: CoinMarketCap API  
    - BREAKER_FIREBASE: Firebase services
    - BREAKER_EMAIL: Email service
    - BREAKER_TELEGRAM: Telegram Bot API
    - BREAKER_NOWPAYMENTS: NOWPayments API
    
    States:
    - CLOSED: Normal operation (requests go through)
    - OPEN: Service failing (requests fail fast, fallback used)
    - HALF_OPEN: Recovery test (some requests allowed to test recovery)
    """
    try:
        from circuit_breaker import CircuitBreakerRegistry
        metrics = CircuitBreakerRegistry.get_metrics()
        return {
            "status": "success",
            "data": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ImportError:
        logger.warning("Circuit breaker module not available")
        return {
            "status": "unavailable",
            "message": "Circuit breaker module not yet integrated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error retrieving circuit breaker status: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.post("/api/metrics/vitals", tags=["monitoring"])
async def record_web_vital(
    name: str,
    value: float,
    url: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    Phase 2: Record Core Web Vitals from frontend.
    Frontend sends this data for performance monitoring.
    
    Parameters:
    - name: Vital name (LCP, FID, CLS, TTFB, FCP)
    - value: Metric value in appropriate units
    - url: (optional) Page URL where vital was measured
    - user_id: (optional) User ID for user-specific analytics
    
    Returns performance status: "good", "poor", or "needs_improvement"
    """
    try:
        vital = performance_metrics.record_vital(name, value)
        return {
            "recorded": True,
            "name": name,
            "value": value,
            "status": vital.status if vital else "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to record vital {name}={value}: {e}")
        return {
            "recorded": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ============================================
# SOCKET.IO ASGI APP (must be at the end after all routes)
# ============================================

# Mount Socket.IO ASGI app for real-time communication
# This wraps the FastAPI app and provides /socket.io/ endpoint
from socketio import ASGIApp
socket_app = ASGIApp(socketio_manager.sio, app)
logger.info("✅ Socket.IO mounted at /socket.io/")

# CRITICAL: Override `app` so uvicorn server:app loads the Socket.IO-wrapped version
app = socket_app
