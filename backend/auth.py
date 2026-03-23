"""
Authentication utilities: JWT tokens, password hashing, 2FA with TOTP.
Production-ready with bcrypt enforcement and pyotp for TOTP verification.

Security Audit Fixes Applied:
- C3: Added jti claim to all JWT tokens
- C5: Token type validation helpers
- C6: Replaced datetime.utcnow() with datetime.now(timezone.utc)
- H1: Refresh token rotation support
- H6: Added aud (audience) claim
"""

from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import secrets
import bcrypt
import logging
import pyotp
from fastapi import Request
from config import settings

logger = logging.getLogger(__name__)

# JWT settings
SECRET_KEY = settings.jwt_secret.get_secret_value()
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.refresh_token_expire_days
JWT_AUDIENCE = "cryptovault-api"
JWT_ISSUER = "cryptovault"

# Enforce bcrypt
try:
    import bcrypt
    logger.info("Using bcrypt for password hashing (production-ready)")
except ImportError as e:
    logger.critical("Bcrypt not installed - install with 'pip install bcrypt'")
    raise RuntimeError("Bcrypt required for secure password hashing") from e

# Enforce pyotp for TOTP
try:
    import pyotp
    logger.info("pyotp available for TOTP 2FA verification")
except ImportError as e:
    logger.critical("pyotp not installed - install with 'pip install pyotp'")
    raise RuntimeError("pyotp required for TOTP 2FA") from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash with timing attack protection."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        )
    except Exception:
        bcrypt.checkpw(b"dummy", bcrypt.gensalt())
        return False


def get_password_hash(password: str) -> str:
    """Hash password with bcrypt (rounds=12)."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with jti, aud, and iss claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": secrets.token_hex(16),
        "aud": JWT_AUDIENCE,
        "iss": JWT_ISSUER,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token with jti, aud, and iss claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "aud": JWT_AUDIENCE,
        "iss": JWT_ISSUER,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = None) -> Optional[Dict]:
    """
    Decode and verify JWT. Validates aud/iss claims.
    Optionally validates token type (access/refresh).
    Returns payload or None.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={
                "require_aud": False,
                "require_iss": False,
            }
        )
        if expected_type and payload.get("type") != expected_type:
            logger.debug(f"Token type mismatch: expected={expected_type}, got={payload.get('type')}")
            return None
        return payload
    except JWTError as e:
        logger.debug(f"Invalid token: {str(e)}")
        return None


def get_token_jti(token: str) -> Optional[str]:
    """Extract jti from a token without full validation (for blacklisting)."""
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_exp": False, "verify_aud": False, "verify_iss": False}
        )
        return payload.get("jti")
    except JWTError:
        return None


def generate_backup_codes(count: int = 8) -> list[str]:
    """Generate one-time backup codes for 2FA."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


def generate_2fa_secret() -> str:
    """Generate base32 secret for TOTP 2FA."""
    return pyotp.random_base32()


def verify_2fa_code(secret: str, code: str, window: int = 1) -> bool:
    """
    Verify TOTP code using pyotp.
    Window allows for clock drift (default +/- 30 seconds).
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=window)


def generate_device_fingerprint(request: Request) -> str:
    """Generate a device fingerprint for suspicious login detection."""
    import hashlib

    ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("user-agent", "")
    accept_language = request.headers.get("accept-language", "")
    accept_encoding = request.headers.get("accept-encoding", "")

    fingerprint_data = f"{ip}:{user_agent}:{accept_language}:{accept_encoding}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()
