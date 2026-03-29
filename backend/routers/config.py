"""
Public runtime configuration endpoint.
Provides frontend-safe settings from backend .env.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from typing import Dict, Any
import logging
from datetime import datetime, timezone

from config import settings
from dependencies import get_current_user_id, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["config"])


def normalize_base_url(value: str) -> str:
    """Normalize base URLs by removing trailing slashes."""
    return value.rstrip("/") if value else value


def derive_request_base_url(request: Request) -> str:
    """Resolve request base URL, respecting proxy headers if present."""
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_proto and forwarded_host:
        return normalize_base_url(f"{forwarded_proto}://{forwarded_host}")
    return normalize_base_url(str(request.base_url))


def derive_ws_base_url(api_base_url: str) -> str:
    """Resolve WS base URL from settings or API base URL."""
    if settings.public_ws_url:
        return normalize_base_url(settings.public_ws_url)
    if api_base_url.startswith("https://"):
        return "wss://" + api_base_url[len("https://"):]
    if api_base_url.startswith("http://"):
        return "ws://" + api_base_url[len("http://"):]
    return api_base_url


@router.get("")
async def get_public_config(request: Request) -> Dict[str, Any]:
    """
    Return frontend-safe runtime configuration.
    This endpoint intentionally excludes secrets.
    """
    request_base_url = derive_request_base_url(request)

    # If the frontend is proxying requests (e.g. Vercel rewrites), prefer same-origin API calls.
    # This avoids cross-site cookie issues and keeps auth stable.
    is_vercel_proxy = (request.headers.get("x-vercel-proxy") or "").lower() == "true"

    api_base_url_setting = normalize_base_url(settings.public_api_url or "")
    prefer_relative_api = is_vercel_proxy or not bool(api_base_url_setting)
    api_base_url = "" if prefer_relative_api else api_base_url_setting

    # When proxying, derive WS base URL from the request origin (same-origin).
    if prefer_relative_api:
        ws_base_url = derive_ws_base_url(request_base_url)
    else:
        ws_base_url = derive_ws_base_url(settings.public_ws_url or api_base_url or request_base_url)
    app_url = normalize_base_url(settings.app_url)
    logo_url = settings.public_logo_url or f"{app_url}/favicon.svg"
    support_email = settings.public_support_email or settings.email_from

    return {
        "appUrl": app_url,
        "apiBaseUrl": api_base_url,
        "preferRelativeApi": prefer_relative_api,
        "wsBaseUrl": ws_base_url,
        "socketIoPath": settings.public_socket_io_path,
        "environment": settings.environment,
        "version": settings.app_version,
        "sentry": {
            "dsn": settings.public_sentry_dsn or "",
            "enabled": bool(settings.public_sentry_dsn),
            "environment": settings.environment,
        },
        "branding": {
            "siteName": settings.public_site_name,
            "logoUrl": logo_url,
            "supportEmail": support_email,
        },
    }


@router.get("/env")
async def get_environment_config(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """
    Get runtime environment configuration (admin-only).
    Shows service health, configuration status, and key metrics.
    """
    # Check if user is admin
    users_collection = db.get_collection("users")
    user = await users_collection.find_one({"id": user_id})
    
    if not user or not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    
    # Check database connectivity
    db_connected = False
    db_response_time = None
    try:
        import time
        start = time.time()
        await db.command("ping")
        db_response_time = (time.time() - start) * 1000
        db_connected = True
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
    
    # Check Redis connectivity (if available)
    redis_connected = False
    redis_response_time = None
    try:
        from redis_cache import redis_cache
        if redis_cache and hasattr(redis_cache, 'health_check'):
            import time
            start = time.time()
            await redis_cache.health_check()
            redis_response_time = (time.time() - start) * 1000
            redis_connected = True
    except Exception as e:
        logger.warning(f"Redis connectivity check: {e}")
    
    # Check email configuration
    email_configured = bool(settings.smtp_host and settings.smtp_password)
    
    return {
        "environment": settings.environment,
        "version": settings.app_version,
        "production_mode": settings.environment == "production",
        "full_production_configuration": settings.full_production_configuration,
        "services": {
            "database": {
                "type": "mongodb",
                "connected": db_connected,
                "response_time_ms": db_response_time,
                "url_configured": bool(settings.mongo_url)
            },
            "cache": {
                "type": "redis",
                "connected": redis_connected,
                "response_time_ms": redis_response_time,
                "url_configured": bool(settings.redis_url or settings.upstash_redis_rest_url)
            },
            "email": {
                "service": settings.email_service,
                "configured": email_configured,
                "from_email": settings.email_from,
                "provider": "SMTP" if settings.email_service == "smtp" else settings.email_service
            }
        },
        "security": {
            "jwt_secret_configured": bool(settings.jwt_secret and len(settings.jwt_secret) >= 32),
            "admin_jwt_secret_configured": bool(settings.admin_jwt_secret and len(settings.admin_jwt_secret) >= 32),
            "csrf_secret_configured": bool(settings.csrf_secret and len(settings.csrf_secret) >= 32),
            "https_enabled": settings.environment == "production",
            "cors_enabled": bool(settings.cors_origins),
            "rate_limiting_enabled": True,
            "two_factor_available": True
        },
        "configuration": {
            "app_url": settings.app_url,
            "public_api_url": settings.public_api_url,
            "public_ws_url": settings.public_ws_url,
            "cors_origins": settings.cors_origins[:3] if settings.cors_origins else [],  # Show first 3
            "environment_name": settings.environment,
            "debug_mode": settings.debug if hasattr(settings, 'debug') else False
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
