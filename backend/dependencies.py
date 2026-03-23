"""Dependency injection for FastAPI endpoints."""

from fastapi import Request, HTTPException, status
from typing import Optional
import logging

from auth import decode_token
from blacklist import is_token_blacklisted

logger = logging.getLogger(__name__)

# Global database connection (set by main app)
_db_connection = None
_limiter = None


def set_db_connection(db):
    """Set global database connection."""
    global _db_connection
    _db_connection = db


def set_limiter(limiter):
    """Set global rate limiter."""
    global _limiter
    _limiter = limiter


def get_db():
    """Get database instance dependency."""
    if not _db_connection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not connected"
        )
    return _db_connection.db


def get_db_connection():
    """Get database connection object dependency."""
    if not _db_connection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not connected"
        )
    return _db_connection


# Make db_connection accessible as module attribute
def __getattr__(name):
    if name == "db_connection":
        return _db_connection
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_limiter():
    """Get rate limiter dependency."""
    if not _limiter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter not initialized"
        )
    return _limiter


async def get_current_user_id(request: Request) -> str:
    """Extract and validate user ID from JWT token."""
    # Try to get token from Authorization header first
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Fall back to cookie
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is blacklisted
    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode and validate token - MUST be an access token (C5 fix)
    payload = decode_token(token, expected_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


async def optional_current_user_id(request: Request) -> Optional[str]:
    """Extract user ID from JWT token if present, otherwise return None."""
    try:
        return await get_current_user_id(request)
    except HTTPException:
        return None
