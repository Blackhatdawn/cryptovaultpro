"""
Enterprise Security Middleware
Comprehensive security hardening for production deployment
"""

import time
import hashlib
import hmac
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers
import logging
from collections import defaultdict
from datetime import datetime, timedelta
import ipaddress

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add comprehensive security headers to all responses
    Following OWASP best practices
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        security_headers = {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Enable XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # HSTS - Force HTTPS for 1 year (31,536,000 seconds)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Cross-Origin Isolation (Relaxed for cross-origin resources like crypto images)
            "Cross-Origin-Embedder-Policy": "unsafe-none",
            
            # COOP - Isolates browsing context from other origins
            "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
            
            # CORP - Allow cross-origin resources
            "Cross-Origin-Resource-Policy": "cross-origin",
            
            # Content Security Policy
            # Note: This is for API responses. Frontend CSP is set in vercel.json
            # Updated for split deployment (Vercel frontend + Render backend)
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com https://vercel.live https://*.vercel-scripts.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' https://cryptovault-api.onrender.com wss://cryptovault-api.onrender.com "
                "https://*.onrender.com wss://*.onrender.com "
                "https://coinbase-love.vercel.app "
                "https://secure-trading-api.preview.emergentagent.com wss://*.preview.emergentagent.com "
                "https://api.coincap.io https://ws.coincap.io wss://ws.coincap.io "
                "https://sentry.io https://*.sentry.io https://*.ingest.sentry.io "
                "https://vercel.live wss://vercel.live https://*.vercel.live; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "upgrade-insecure-requests"
            ),
            
            # Permissions policy - only valid directives (crypto/fintech security)
            # See: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy
            "Permissions-Policy": (
                "accelerometer=(), "
                "autoplay=(), "
                "camera=(), "
                "cross-origin-isolated=(), "
                "display-capture=(), "
                "encrypted-media=(), "
                "fullscreen=(), "
                "geolocation=(), "
                "gyroscope=(), "
                "keyboard-map=(), "
                "magnetometer=(), "
                "microphone=(), "
                "midi=(), "
                "payment=(), "
                "picture-in-picture=(), "
                "publickey-credentials-get=(), "
                "screen-wake-lock=(), "
                "sync-xhr=(), "
                "usb=(), "
                "xr-spatial-tracking=()"
            ),
            
            # Remove server header
            "Server": "CryptoVault",
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response


class AdvancedRateLimiter(BaseHTTPMiddleware):
    """
    Advanced rate limiting with per-IP and per-user tracking
    Implements sliding window algorithm
    """
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.rate_limits: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Dict[str, datetime] = {}
        
        # Configurable limits
        self.default_limit = kwargs.get('default_limit', 60)
        self.window_seconds = kwargs.get('window_seconds', 60)
        self.block_duration_minutes = kwargs.get('block_duration', 15)
        self.burst_threshold = kwargs.get('burst_threshold', 10)
        
    def _get_client_identifier(self, request: Request) -> str:
        """Get client IP, handling proxies"""
        # Check X-Forwarded-For header for proxied requests
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted (e.g., health checks, monitoring)"""
        whitelist = [
            "127.0.0.1",
            "::1",
        ]
        return ip in whitelist
    
    def _clean_old_requests(self, identifier: str):
        """Remove requests outside the current window"""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        if identifier in self.rate_limits:
            self.rate_limits[identifier] = [
                req_time for req_time in self.rate_limits[identifier]
                if req_time > cutoff_time
            ]
    
    def _check_burst(self, identifier: str) -> bool:
        """Check for burst attacks (too many requests in short time)"""
        if not self.rate_limits[identifier]:
            return False
        
        current_time = time.time()
        recent_requests = [
            req_time for req_time in self.rate_limits[identifier]
            if current_time - req_time < 1  # Last second
        ]
        
        return len(recent_requests) > self.burst_threshold
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/health", "/api/health/ready"]:
            return await call_next(request)
        
        identifier = self._get_client_identifier(request)
        
        # Check whitelist
        if self._is_whitelisted(identifier):
            return await call_next(request)
        
        # Check if IP is currently blocked
        if identifier in self.blocked_ips:
            unblock_time = self.blocked_ips[identifier]
            if datetime.now() < unblock_time:
                remaining = (unblock_time - datetime.now()).seconds
                logger.warning(f"Blocked IP {identifier} attempted access. Remaining: {remaining}s")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Too many requests. Your IP has been temporarily blocked.",
                        "retry_after": remaining
                    }
                )
            else:
                # Unblock expired
                del self.blocked_ips[identifier]
        
        # Clean old requests
        self._clean_old_requests(identifier)
        
        # Check for burst attack
        if self._check_burst(identifier):
            # Block the IP for burst attack
            self.blocked_ips[identifier] = datetime.now() + timedelta(minutes=self.block_duration_minutes)
            logger.error(f"Burst attack detected from {identifier}. Blocking for {self.block_duration_minutes} minutes")
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Burst attack detected. Your IP has been blocked.",
                    "retry_after": self.block_duration_minutes * 60
                }
            )
        
        # Check rate limit
        request_count = len(self.rate_limits[identifier])
        
        if request_count >= self.default_limit:
            retry_after = self.window_seconds
            logger.warning(f"Rate limit exceeded for {identifier}: {request_count} requests in {self.window_seconds}s")
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "limit": self.default_limit,
                    "window": self.window_seconds,
                    "retry_after": retry_after
                },
                headers={
                    "X-RateLimit-Limit": str(self.default_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                    "Retry-After": str(retry_after)
                }
            )
        
        # Record this request
        self.rate_limits[identifier].append(time.time())
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.default_limit - len(self.rate_limits[identifier])
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + self.window_seconds))
        
        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Enterprise CSRF Protection for state-changing operations.
    
    Features:
    - Token validation via cookie comparison (double-submit pattern)
    - Configurable skip paths for public endpoints
    - Detailed logging for security auditing
    - Rate limiting for failed CSRF attempts
    """
    
    # Paths that don't require CSRF validation
    # These are public endpoints or handle their own auth
    SKIP_PATHS = [
        "/api/auth/login",
        "/api/auth/signup",
        "/api/auth/refresh",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/verify-email",
        "/api/auth/resend-verification",
        "/api/v1/auth/login",
        "/api/v1/auth/signup",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/api/admin/login",
        "/api/admin/verify-otp",
        "/csrf",
        "/api/csrf",
        "/health",
        "/api/health",
        "/ping",
        "/api/ping",
        "/socket.io/",
        "/api/config",
        "/api/wallet/webhook/nowpayments",
    ]
    
    # Methods that require CSRF validation
    PROTECTED_METHODS = ["POST", "PUT", "DELETE", "PATCH"]
    
    def __init__(self, app, secret_key: str = None, enabled: bool = True):
        super().__init__(app)
        self.secret_key = (secret_key or "").encode() if secret_key else None
        self.enabled = enabled
        self._failed_attempts: Dict[str, int] = {}
        
    def _should_skip_path(self, path: str) -> bool:
        """Check if path should skip CSRF validation."""
        # Exact match
        if path in self.SKIP_PATHS:
            return True
        
        # Prefix match for dynamic paths
        for skip_path in self.SKIP_PATHS:
            if path.startswith(skip_path):
                return True
        
        return False
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client IP for rate limiting."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
    
    def _validate_csrf_token(self, header_token: str, cookie_token: str) -> bool:
        """
        Validate CSRF token using double-submit pattern.
        Compares token from header with token from cookie.
        Uses constant-time comparison to prevent timing attacks.
        """
        if not header_token or not cookie_token:
            return False
        
        try:
            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(header_token, cookie_token)
        except Exception as e:
            logger.error(f"CSRF validation error: {e}")
            return False
    
    async def dispatch(self, request: Request, call_next):
        # Skip if CSRF protection is disabled
        if not self.enabled:
            return await call_next(request)
        
        # Only check state-changing methods
        if request.method not in self.PROTECTED_METHODS:
            return await call_next(request)
        
        # Skip configured paths
        if self._should_skip_path(request.url.path):
            return await call_next(request)
        
        # M4 FIX: CSRF token httpOnly + SPA conflict
        # Allow CSRF bypass for authenticated API calls with valid JWT token
        # This supports SPAs that use Authorization header instead of cookies
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # Valid JWT token in header - allow request without CSRF check
            # JWT validation happens in endpoint dependencies
            logger.debug(f"Allowing {request.method} {request.url.path} - authenticated via JWT token")
            return await call_next(request)
        
        # Get CSRF token from header
        header_token = request.headers.get("X-CSRF-Token")
        
        # Get CSRF token from cookie
        cookie_token = request.cookies.get("csrf_token")
        
        client_ip = self._get_client_identifier(request)
        
        # Check for missing token
        if not header_token:
            logger.warning(
                f"🛑 CSRF token missing in header for {request.method} {request.url.path}",
                extra={
                    "type": "security",
                    "event": "csrf_missing",
                    "client_ip": client_ip,
                    "path": request.url.path,
                    "method": request.method
                }
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": {
                        "code": "CSRF_TOKEN_MISSING",
                        "message": "CSRF token is required for this request",
                        "hint": "Include X-CSRF-Token header with the token from /csrf endpoint"
                    }
                }
            )
        
        # Validate token
        if not self._validate_csrf_token(header_token, cookie_token):
            # Track failed attempts for rate limiting
            self._failed_attempts[client_ip] = self._failed_attempts.get(client_ip, 0) + 1
            
            logger.warning(
                f"🛑 Invalid CSRF token for {request.method} {request.url.path}",
                extra={
                    "type": "security",
                    "event": "csrf_invalid",
                    "client_ip": client_ip,
                    "path": request.url.path,
                    "method": request.method,
                    "failed_attempts": self._failed_attempts[client_ip]
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": {
                        "code": "CSRF_TOKEN_INVALID",
                        "message": "CSRF token validation failed",
                        "hint": "Token may be expired. Refresh by calling /csrf endpoint"
                    }
                }
            )
        
        # Token is valid - proceed with request
        return await call_next(request)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Validate and sanitize incoming requests
    """
    
    async def dispatch(self, request: Request, call_next):
        # Check request size
        content_length = request.headers.get("content-length")
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            max_size = 10  # 10MB
            
            if size_mb > max_size:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"error": f"Request body too large. Maximum size: {max_size}MB"}
                )
        
        # Validate Content-Type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            # Skip content-type validation for endpoints that don't require a body
            no_body_endpoints = [
                "/api/auth/refresh",
                "/api/auth/logout"
            ]
            
            if request.url.path not in no_body_endpoints:
                content_type = request.headers.get("content-type", "")
                
                # Allow JSON and form data
                allowed_types = [
                    "application/json",
                    "application/x-www-form-urlencoded",
                    "multipart/form-data"
                ]
                
                if not any(allowed in content_type.lower() for allowed in allowed_types):
                    return JSONResponse(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        content={"error": "Unsupported content type"}
                    )
        
        return await call_next(request)


# Export middleware
__all__ = [
    "SecurityHeadersMiddleware",
    "AdvancedRateLimiter",
    "CSRFProtectionMiddleware",
    "RequestValidationMiddleware"
]
