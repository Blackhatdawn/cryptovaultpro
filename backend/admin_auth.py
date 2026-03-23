"""
Admin Authentication and Authorization System
Enterprise-grade admin control panel security with OTP
"""

import logging
import secrets
import hashlib
import hmac
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps

from fastapi import HTTPException, Request, Depends, status
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, Field, EmailStr

from config import settings
from database import get_database

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Admin JWT settings - C1 FIX: Use HMAC-derived key independent from user JWT
_user_secret = settings.jwt_secret.get_secret_value()
ADMIN_SECRET_KEY = hmac.new(
    _user_secret.encode(),
    b"cryptovault-admin-jwt-signing-key-v1",
    hashlib.sha256,
).hexdigest()
ADMIN_TOKEN_EXPIRE_HOURS = 8  # Admin sessions expire faster


class AdminUser(BaseModel):
    """Admin user model"""
    id: str
    email: EmailStr
    name: str
    role: str = "admin"  # admin, super_admin
    permissions: List[str] = []
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None
    

class AdminLoginRequest(BaseModel):
    """Admin login request"""
    email: EmailStr
    password: str
    totp_code: Optional[str] = None


class AdminOTPVerifyRequest(BaseModel):
    """Admin OTP verification request"""
    email: EmailStr
    otp_code: str


class AdminLoginResponse(BaseModel):
    """Admin login response"""
    admin: Dict[str, Any]
    token: str
    expires_at: datetime
    requires_otp: Optional[bool] = False  # Indicates if OTP is required


# Default admin permissions
ADMIN_PERMISSIONS = {
    "super_admin": [
        "users:read", "users:write", "users:delete", "users:suspend",
        "wallets:read", "wallets:write", "wallets:adjust",
        "transactions:read", "transactions:void", "transactions:refund",
        "system:read", "system:write", "system:config",
        "admins:read", "admins:write", "admins:delete",
        "audit:read", "audit:export",
        "reports:read", "reports:export"
    ],
    "admin": [
        "users:read", "users:write", "users:suspend",
        "wallets:read", "wallets:adjust",
        "transactions:read", "transactions:void",
        "system:read",
        "audit:read",
        "reports:read"
    ],
    "moderator": [
        "users:read", "users:suspend",
        "wallets:read",
        "transactions:read",
        "audit:read"
    ]
}


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_admin_otp() -> Tuple[str, datetime]:
    """
    Generate a 6-digit OTP code for admin authentication.
    C4 FIX: Uses secrets.choice for cryptographic randomness.
    Returns: (otp_code, expiration_time)
    """
    otp_code = ''.join(secrets.choice(string.digits) for _ in range(6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)  # 5-minute expiry
    return otp_code, expires_at


def create_admin_token(admin_id: str, email: str, role: str) -> tuple[str, datetime]:
    """Create an admin JWT token"""
    expires = datetime.now(timezone.utc) + timedelta(hours=ADMIN_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": admin_id,
        "email": email,
        "role": role,
        "type": "admin",
        "exp": expires,
        "iat": datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, ADMIN_SECRET_KEY, algorithm=settings.jwt_algorithm)
    return token, expires


def decode_admin_token(token: str) -> Optional[Dict]:
    """Decode and verify an admin JWT token"""
    try:
        payload = jwt.decode(token, ADMIN_SECRET_KEY, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "admin":
            return None
        return payload
    except JWTError as e:
        logger.warning(f"Admin token decode error: {e}")
        return None


async def get_current_admin(request: Request) -> Dict:
    """
    Dependency to get the current authenticated admin.
    Checks both cookie and Authorization header.
    """
    from dependencies import get_db
    
    # Try cookie first
    token = request.cookies.get("admin_token")
    
    # Then try Authorization header
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required"
        )
    
    payload = decode_admin_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token"
        )
    
    # Verify admin still exists and is active
    try:
        db = get_db()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        )
    
    admin = await db.admins.find_one({"id": payload["sub"], "is_active": True})
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found or deactivated"
        )
    
    return {
        "id": admin["id"],
        "email": admin["email"],
        "name": admin["name"],
        "role": admin["role"],
        "permissions": admin.get("permissions", ADMIN_PERMISSIONS.get(admin["role"], []))
    }


def require_permission(permission: str):
    """Decorator to require a specific permission"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get admin from kwargs (injected by Depends)
            admin = kwargs.get("current_admin")
            if not admin:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin authentication required"
                )
            
            permissions = admin.get("permissions", [])
            if permission not in permissions and admin.get("role") != "super_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission} required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def create_default_admin():
    """Create default super admin if none exists"""
    from dependencies import get_db
    
    try:
        db = get_db()
    except Exception as e:
        logger.warning(f"Database not ready for admin initialization: {e}")
        return
    
    # Check if any admin exists
    existing = await db.admins.find_one({})
    if existing:
        logger.info("✅ Admin account already exists")
        return

    # Production safety guard: never create predictable default admin implicitly.
    bootstrap_allowed = str(getattr(settings, "admin_bootstrap_enabled", "false")).lower() in {"1", "true", "yes"}
    if settings.environment == "production" and not bootstrap_allowed:
        logger.warning("⚠️ Skipping default admin bootstrap in production (ADMIN_BOOTSTRAP_ENABLED not true)")
        return

    # Create bootstrap admin
    admin_id = secrets.token_hex(16)
    default_password = secrets.token_urlsafe(18)
    
    admin_doc = {
        "id": admin_id,
        "email": "admin@cryptovault.financial",
        "password_hash": hash_password(default_password),
        "name": "Super Admin",
        "role": "super_admin",
        "permissions": ADMIN_PERMISSIONS["super_admin"],
        "is_active": True,
        "require_password_change": True,
        "created_at": datetime.now(timezone.utc),
        "last_login": None,
        "login_history": [],
        "two_factor_enabled": False,
        "two_factor_secret": None
    }
    
    await db.admins.insert_one(admin_doc)
    logger.info("=" * 60)
    logger.info("🔐 BOOTSTRAP ADMIN ACCOUNT CREATED")
    logger.info("   Email: admin@cryptovault.financial")
    logger.warning("   A random bootstrap password was generated. Retrieve it from secure deployment secrets/log pipeline and rotate immediately.")
    logger.info("   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")
    logger.info("=" * 60)


async def log_admin_action(
    admin_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Dict[str, Any],
    ip_address: str = None
):
    """Log admin actions for audit trail"""
    from dependencies import get_db
    
    try:
        db = get_db()
    except Exception:
        logger.warning("Cannot log admin action - database not connected")
        return
    
    log_entry = {
        "id": secrets.token_hex(16),
        "admin_id": admin_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": ip_address,
        "timestamp": datetime.now(timezone.utc),
        "type": "admin_action"
    }
    
    await db.admin_audit_logs.insert_one(log_entry)
    logger.info(f"Admin action logged: {action} on {resource_type}/{resource_id}")
