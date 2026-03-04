"""
Enterprise-Grade Configuration Management for CryptoVault Backend

Uses pydantic-settings for robust environment variable handling with:
- Type validation
- Default values
- Custom validators
- Environment variable override support
- Production-ready startup validation

Usage:
    from config import settings, validate_startup_environment
    
    # Validate on startup
    validate_startup_environment()
    
    print(settings.mongo_url)
    print(settings.upstash_redis_rest_url)
"""

from typing import Optional, List
from functools import lru_cache
from pathlib import Path

from pydantic import Field, validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing trailing slashes and ensuring proper format.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL without trailing slashes
    """
    if not url:
        return url
    
    # Remove trailing slashes but keep single slash for root
    if url != "/" and url.endswith("/"):
        url = url.rstrip("/")
    
    return url


def normalize_socket_io_path(path: str) -> str:
    """
    Normalize Socket.IO path to ensure it starts with / and ends with /.
    
    Args:
        path: Socket.IO path to normalize
        
    Returns:
        Normalized Socket.IO path
    """
    if not path:
        return "/socket.io/"
    
    # Ensure path starts with /
    if not path.startswith("/"):
        path = "/" + path
    
    # Ensure path ends with /
    if not path.endswith("/"):
        path = path + "/"
    
    return path


def get_version_from_file() -> str:
    """Reads the version from the VERSION file."""
    try:
        return (Path(__file__).parent.parent / "VERSION").read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


class Settings(BaseSettings):
    """
    Application settings using pydantic BaseSettings.
    
    Environment variables override defaults.
    Priority order:
    1. Environment variables
    2. .env file values
    3. Hardcoded defaults
    """

    # ============================================
    # APPLICATION CONFIGURATION
    # ============================================
    app_name: str = Field(default="CryptoVault", description="Application name")
    app_version: str = Field(default_factory=get_version_from_file, description="Application version")
    environment: str = Field(
        default="development",
        description="Environment: development, staging, production"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    full_production_configuration: bool = Field(
        default=False,
        description="When true in production, enforce strict checks for all integration-critical env vars"
    )
    app_url: str = Field(
        default="https://www.cryptovault.financial",
        description="Frontend application URL"
    )
    public_site_name: str = Field(
        default="CryptoVault Financial",
        description="Public site name for frontend branding"
    )
    public_logo_url: Optional[str] = Field(
        default=None,
        description="Public logo URL for frontend branding"
    )
    public_support_email: Optional[str] = Field(
        default=None,
        description="Public support email for frontend"
    )
    public_api_url: Optional[str] = Field(
        default=None,
        description="Public API base URL for frontend runtime config"
    )
    public_ws_url: Optional[str] = Field(
        default=None,
        description="Public WebSocket base URL for frontend runtime config"
    )
    public_socket_io_path: str = Field(
        default="/socket.io/",
        description="Socket.IO path for frontend clients"
    )
    public_sentry_dsn: Optional[str] = Field(
        default=None,
        description="Public Sentry DSN for frontend monitoring"
    )

    # ============================================
    # SERVER CONFIGURATION
    # ============================================
    host: str = Field(default="0.0.0.0", description="Server host binding")
    port: int = Field(
        default=8000,
        description="Server port (falls back to PORT env var for Render/Railway)"
    )
    workers: int = Field(default=4, description="Number of Gunicorn workers for production")

    # ============================================
    # MONGODB CONFIGURATION
    # ============================================
    mongo_url: str = Field(
        default="",
        description="MongoDB Atlas connection URL (REQUIRED - set in environment)"
    )
    db_name: str = Field(default="cryptovault", description="Database name")
    mongo_max_pool_size: int = Field(default=10, description="MongoDB connection pool size")
    mongo_timeout_ms: int = Field(default=5000, description="MongoDB connection timeout in ms")

    # ============================================
    # REDIS / CACHE CONFIGURATION
    # ============================================
    use_redis: bool = Field(default=True, description="Enable Redis caching")
    upstash_redis_rest_url: Optional[str] = Field(
        default=None,
        description="Upstash Redis REST API URL (for serverless environments)"
    )
    upstash_redis_rest_token: Optional[str] = Field(
        default=None,
        description="Upstash Redis REST API token"
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Traditional Redis URL (if not using Upstash)"
    )
    redis_prefix: str = Field(default="cryptovault:", description="Redis key prefix")

    # ============================================
    # SECURITY & AUTHENTICATION
    # ============================================
    jwt_secret: SecretStr = Field(
        default="change-me-in-production",
        description="JWT signing secret key"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration in minutes")
    refresh_token_expire_days: int = Field(default=7, description="Refresh token expiration in days")
    
    csrf_secret: SecretStr = Field(
        default="change-me-in-production",
        description="CSRF protection secret"
    )
    use_cross_site_cookies: bool = Field(
        default=False,
        description="Enable cross-site cookies for development"
    )

    # ============================================
    # CORS CONFIGURATION
    # ============================================
    cors_origins: List[str] = Field(
        default=[],
        description="List of allowed CORS origins. Can be set via comma-separated string or JSON array in env."
    )

    # ============================================
    # EMAIL CONFIGURATION
    # ============================================
    email_service: str = Field(default="sendgrid", description="Email service provider (sendgrid, resend, smtp, mock)")
    sendgrid_api_key: Optional[SecretStr] = Field(
        default=None,
        description="SendGrid API key"
    )
    resend_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Resend API key"
    )
    email_from: str = Field(
        default="team@cryptovault.financial",
        description="Default sender email"
    )
    email_from_name: str = Field(
        default="CryptoVault Financial",
        description="Default sender name"
    )
    email_verification_url: str = Field(
        default="https://cryptovault.financial/verify",
        description="Email verification URL"
    )
    smtp_host: Optional[str] = Field(default=None, description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[SecretStr] = Field(default=None, description="SMTP password")
    smtp_use_tls: bool = Field(default=True, description="Use STARTTLS for SMTP connections")
    smtp_use_ssl: bool = Field(default=False, description="Use implicit SSL/TLS for SMTP connections")

    # ============================================
    # EXTERNAL CRYPTO SERVICES
    # ============================================
    coincap_api_key: Optional[str] = Field(
        default=None,
        description="CoinCap API key for higher rate limits"
    )
    coincap_api_url: str = Field(
        default="https://api.coincap.io/v2",
        description="CoinCap API base URL"
    )
    coincap_ws_url: str = Field(
        default="wss://ws.coincap.io/prices",
        description="CoinCap WebSocket URL for real-time prices"
    )
    coincap_rate_limit: int = Field(default=50, description="CoinCap API rate limit per minute")
    use_mock_prices: bool = Field(default=False, description="Use mock price data for testing")
    allow_mock_payment_fallback: bool = Field(
        default=False,
        description="Allow NOWPayments mock fallback when API key is missing"
    )
    
    # NowPayments (Payment Processing)
    nowpayments_api_key: Optional[SecretStr] = Field(
        default=None,
        description="NowPayments API key"
    )
    nowpayments_ipn_secret: Optional[SecretStr] = Field(
        default=None,
        description="NowPayments IPN secret"
    )
    nowpayments_sandbox: bool = Field(default=False, description="Use NowPayments sandbox")

    # ============================================
    # FEATURE FLAGS
    # ============================================
    feature_2fa_enabled: bool = Field(default=True, description="Enable 2FA endpoints")
    feature_deposits_enabled: bool = Field(default=True, description="Enable deposit endpoints")
    feature_withdrawals_enabled: bool = Field(default=True, description="Enable withdrawal endpoints")
    feature_transfers_enabled: bool = Field(default=True, description="Enable transfer endpoints")
    feature_trading_enabled: bool = Field(default=True, description="Enable trading endpoints")
    feature_staking_enabled: bool = Field(default=False, description="Enable staking/earn endpoints")

    # ============================================
    # FIREBASE CONFIGURATION
    # ============================================
    firebase_credentials_path: Optional[str] = Field(
        default=None,
        description="Path to Firebase credentials JSON file"
    )
    firebase_credential: Optional[str] = Field(
        default=None,
        description="Firebase credentials as JSON string (alternative to file)"
    )

    # ============================================
    # TELEGRAM BOT (Free KYC Notifications)
    # ============================================
    telegram_enabled: bool = Field(
        default=True,
        description="Enable Telegram bot notifications and command polling"
    )
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot token for admin notifications (get from @BotFather)"
    )
    admin_telegram_chat_id: Optional[str] = Field(
        default=None,
        description="Telegram chat ID(s) for admin notifications (comma-separated for multiple devices)"
    )

    # ============================================
    # ERROR TRACKING (Sentry)
    # ============================================
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )
    sentry_traces_sample_rate: float = Field(
        default=0.1,
        description="Sentry tracing sample rate (0.0-1.0)"
    )
    sentry_profiles_sample_rate: float = Field(
        default=0.1,
        description="Sentry profiling sample rate (0.0-1.0)"
    )

    # ============================================
    # RATE LIMITING
    # ============================================
    rate_limit_per_minute: int = Field(
        default=60,
        description="Requests allowed per minute"
    )

    # ============================================
    # LOGGING
    # ============================================
    log_level: str = Field(default="INFO", description="Logging level")

    # Pydantic Settings configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    # ============================================
    # VALIDATORS
    # ============================================

    @validator("port", pre=True)
    def validate_port(cls, v):
        """
        Validate port number. Supports PORT env var for Render/Railway compatibility.
        """
        if v is None:
            return 8000
        port = int(v)
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        return port

    @validator("cors_origins", pre=True)
    def validate_cors_origins(cls, v):
        """
        Parse CORS origins from various formats into a list of strings.
        Handles:
        - A list of strings (no change)
        - A comma-separated string ("http://a.com,http://b.com")
        - A JSON array string ('["http://a.com", "http://b.com"]')
        - None or empty values (returns empty list)
        """
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v.strip():
                return []
            # Handle JSON-encoded list
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    return json.loads(v)
                except json.JSONDecodeError:
                    # Fallback for malformed JSON, treat as string
                    pass
            # Handle comma-separated string
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        # If it's not a recognized type, return an empty list to prevent errors
        return []

    @validator("environment")
    def validate_environment(cls, v):
        """Ensure environment is one of valid values (case-insensitive)."""
        valid_envs = ["development", "staging", "production"]
        value = str(v).strip().lower()
        if value not in valid_envs:
            raise ValueError(f"Environment must be one of {valid_envs}, got {v}")
        return value

    @validator("log_level")
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}, got {v}")
        return v.upper()

    @validator("email_service")
    def validate_email_service(cls, v):
        """Ensure email service provider is valid."""
        value = str(v).strip().lower()
        valid_services = ["sendgrid", "resend", "smtp", "mock"]
        if value not in valid_services:
            raise ValueError(f"Email service must be one of {valid_services}, got {v}")
        return value

    @validator("smtp_host", "smtp_username", pre=True)
    def normalize_optional_smtp_strings(cls, v):
        """Convert blank SMTP text fields to None for predictable validation."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @validator("smtp_password", pre=True)
    def normalize_optional_smtp_password(cls, v):
        """Convert blank SMTP password values to None."""
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None

        get_secret_value = getattr(v, "get_secret_value", None)
        if callable(get_secret_value):
            raw = get_secret_value()
            if isinstance(raw, str) and not raw.strip():
                return None
        return v

    @validator("smtp_port")
    def validate_smtp_port(cls, v):
        """Ensure SMTP port is within valid TCP range."""
        port = int(v)
        if not (1 <= port <= 65535):
            raise ValueError(f"SMTP port must be between 1 and 65535, got {v}")
        return port

    @validator("smtp_password")
    def validate_smtp_credentials_pair(cls, v, values):
        """Ensure SMTP username/password are configured as a pair when auth is used."""
        username = values.get("smtp_username")
        has_username = bool(username)
        has_password = bool(v)

        if has_username != has_password:
            raise ValueError("smtp_username and smtp_password must be provided together")
        return v

    @validator("smtp_use_ssl")
    def validate_smtp_tls_mode(cls, v, values):
        """Prevent conflicting SMTP TLS configuration."""
        smtp_use_tls = bool(values.get("smtp_use_tls", True))
        if smtp_use_tls and bool(v):
            raise ValueError("smtp_use_tls and smtp_use_ssl cannot both be true")
        return v

    @validator("sendgrid_api_key")
    def validate_production_email_config(cls, v, values):
        """
        FIX #3: Validate email configuration in production.
        Ensure production environments have properly configured email service.
        """
        environment = values.get("environment", "development")
        email_service = values.get("email_service", "mock")
        
        # Only enforce in production
        if environment == "production":
            if email_service == "sendgrid":
                # SendGrid requires API key
                if not v:
                    raise ValueError(
                        "CRITICAL: SENDGRID_API_KEY is required when EMAIL_SERVICE=sendgrid in production. "
                        "Either set SENDGRID_API_KEY or change EMAIL_SERVICE to 'smtp'."
                    )
            elif email_service == "resend":
                if not values.get("resend_api_key"):
                    raise ValueError(
                        "CRITICAL: RESEND_API_KEY is required when EMAIL_SERVICE=resend in production. "
                        "Either set RESEND_API_KEY or change EMAIL_SERVICE to 'smtp' or 'sendgrid'."
                    )
            elif email_service == "smtp":
                # SMTP requires host (username/password validated separately)
                smtp_host = values.get("smtp_host")
                if not smtp_host:
                    raise ValueError(
                        "CRITICAL: SMTP_HOST is required when EMAIL_SERVICE=smtp in production. "
                        "Either set SMTP_HOST or change EMAIL_SERVICE to 'sendgrid'."
                    )
            elif email_service == "mock":
                # Mock email not allowed in production
                raise ValueError(
                    "CRITICAL: Mock email service is not allowed in production. "
                    "Set EMAIL_SERVICE to 'sendgrid', 'resend', or 'smtp' and provide credentials."
                )
        
        return v

    @validator("app_url", "public_api_url", "public_ws_url", pre=True)
    def normalize_urls(cls, v):
        """Normalize URLs by removing trailing slashes."""
        if isinstance(v, str) and v:
            return normalize_url(v)
        return v

    @validator("public_socket_io_path", pre=True)
    def normalize_socket_path(cls, v):
        """Normalize Socket.IO path to ensure proper format."""
        if isinstance(v, str):
            return normalize_socket_io_path(v)
        return v

    # ============================================
    # PROPERTIES
    # ============================================

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging."""
        return self.environment == "staging"

    def get_cors_origins_list(self) -> List[str]:
        """Get CORS origins as a normalized, de-duplicated list."""
        if isinstance(self.cors_origins, str):
            origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        else:
            origins = [origin.strip() for origin in self.cors_origins if isinstance(origin, str) and origin.strip()]

        # Preserve order while removing duplicates
        return list(dict.fromkeys(origins))

    def get_socketio_cors_origins(self) -> List[str]:
        """Get Socket.IO CORS origins with app URL and deployment URLs."""
        origins = self.get_cors_origins_list()
        # Always include app URL
        app_origin = self.app_url.rstrip("/")
        if app_origin and app_origin not in origins:
            origins.append(app_origin)
        # Always include the public API URL (Render domain) for same-origin WS
        api_origin = self.public_api_url.rstrip("/") if self.public_api_url else ""
        if api_origin and api_origin not in origins:
            origins.append(api_origin)
        return origins

    def is_sentry_available(self) -> bool:
        """Check if Sentry is configured with a valid DSN."""
        return bool(self.sentry_dsn and str(self.sentry_dsn).strip())

    @property
    def rate_limit_requests_per_minute(self) -> int:
        """Backward-compatible rate limit accessor."""
        return self.rate_limit_per_minute

    @property
    def password_algorithm(self) -> str:
        """Backward-compatible JWT algorithm accessor."""
        return self.jwt_algorithm

    @property
    def database_url(self) -> str:
        """Backward-compatible database URL accessor."""
        return self.mongo_url

    def get_redis_url(self) -> Optional[str]:
        """
        Get Redis URL from Upstash REST API or traditional Redis.
        
        Priority:
        1. Upstash REST API (for serverless)
        2. Traditional Redis URL
        """
        if self.upstash_redis_rest_url and self.upstash_redis_rest_token:
            return self.upstash_redis_rest_url
        return self.redis_url

    def is_redis_available(self) -> bool:
        """Check if Redis is configured."""
        return bool(
            (self.upstash_redis_rest_url and self.upstash_redis_rest_token)
            or self.redis_url
        )

    def to_dict(self, include_secrets: bool = False) -> dict:
        """
        Convert settings to dictionary.
        
        Args:
            include_secrets: If True, include secret values (use with caution)
        
        Returns:
            Dictionary representation of settings
        """
        data = self.model_dump(exclude_unset=False)
        
        if not include_secrets:
            # Redact secrets
            secret_fields = {
                "jwt_secret",
                "csrf_secret",
                "sendgrid_api_key",
                "resend_api_key",
                "nowpayments_api_key",
                "nowpayments_ipn_secret",
                "upstash_redis_rest_token",
                "firebase_credential"
            }
            for field in secret_fields:
                if field in data:
                    data[field] = "***REDACTED***"
        
        return data

    def __repr__(self) -> str:
        """String representation of settings."""
        return (
            f"<Settings "
            f"environment={self.environment} "
            f"app={self.app_name} "
            f"v={self.app_version} "
            f"host={self.host}:{self.port}>"
        )


# ============================================
# GLOBAL SETTINGS INSTANCE
# ============================================

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure only one instance is created.
    """
    return Settings()


# Create global settings instance
settings = get_settings()


# ============================================
# STARTUP VALIDATION
# ============================================

def validate_startup_environment() -> dict:
    """
    Validate all critical environment variables on startup.

    This function should be called in your FastAPI startup event.
    Raises ValueError if critical configuration is missing in production.

    Returns:
        Dictionary with validation results
    """
    critical_vars = {
        "jwt_secret": settings.jwt_secret,
        "csrf_secret": settings.csrf_secret,
        "mongo_url": settings.mongo_url,
    }

    missing_vars = []
    for var_name, var_value in critical_vars.items():
        if not var_value or var_value == "change-me-in-production":
            if settings.is_production:
                missing_vars.append(var_name)

    strict_missing_vars = []

    if settings.is_production and settings.full_production_configuration:
        # Frontend/backend sync guardrails
        strict_required = {
            "app_url": settings.app_url,
            "public_api_url": settings.public_api_url,
            "public_ws_url": settings.public_ws_url,
            "public_socket_io_path": settings.public_socket_io_path,
            "cors_origins": settings.get_cors_origins_list(),
        }

        if settings.email_service == "sendgrid":
            strict_required["sendgrid_api_key"] = settings.sendgrid_api_key
        elif settings.email_service == "resend":
            strict_required["resend_api_key"] = settings.resend_api_key
        elif settings.email_service == "smtp":
            strict_required["smtp_host"] = settings.smtp_host
            strict_required["smtp_port"] = settings.smtp_port

        if not settings.allow_mock_payment_fallback:
            strict_required["nowpayments_api_key"] = settings.nowpayments_api_key
            strict_required["nowpayments_ipn_secret"] = settings.nowpayments_ipn_secret

        if not settings.use_mock_prices:
            strict_required["coincap_api_key"] = settings.coincap_api_key

        if settings.use_redis:
            has_upstash = bool(settings.upstash_redis_rest_url and settings.upstash_redis_rest_token)
            has_redis = bool(settings.redis_url)
            if not (has_upstash or has_redis):
                strict_missing_vars.append("upstash_redis_rest_url/upstash_redis_rest_token OR redis_url")

        if settings.telegram_enabled:
            strict_required["telegram_bot_token"] = settings.telegram_bot_token
            strict_required["admin_telegram_chat_id"] = settings.admin_telegram_chat_id

        for var_name, var_value in strict_required.items():
            is_empty_list = isinstance(var_value, list) and len(var_value) == 0
            if not var_value or is_empty_list:
                strict_missing_vars.append(var_name)

        cors_origins = settings.get_cors_origins_list()
        app_origin = settings.app_url.rstrip("/") if settings.app_url else ""
        if app_origin and app_origin not in cors_origins:
            strict_missing_vars.append("cors_origins must include APP_URL origin")

        if settings.public_api_url and not str(settings.public_api_url).startswith(("https://", "http://")):
            strict_missing_vars.append("public_api_url must be http(s) URL")
        if settings.public_ws_url and not str(settings.public_ws_url).startswith(("wss://", "ws://")):
            strict_missing_vars.append("public_ws_url must be ws(s) URL")

        if settings.public_socket_io_path and not str(settings.public_socket_io_path).startswith("/"):
            strict_missing_vars.append("public_socket_io_path must start with '/'")

    if missing_vars or strict_missing_vars:
        combined = missing_vars + strict_missing_vars
        error_msg = (
            "❌ STARTUP FAILED: Critical environment variables not configured:\\n"
            f"   {', '.join(combined)}\\n\\n"
            "   Please set these in your environment or .env file:\\n"
        )
        for var in combined:
            error_msg += f"   - {str(var).upper()}\\n"
        raise ValueError(error_msg)

    # Log successful validation
    print("✅ Environment Validated")
    print(f"   Environment: {settings.environment}")
    print(f"   App: {settings.app_name} v{settings.app_version}")
    print(f"   Host: {settings.host}:{settings.port}")
    print(f"   Database: {settings.db_name}")
    print(f"   Redis: {'Enabled (Upstash)' if settings.upstash_redis_rest_url else 'Enabled (Standard)' if settings.redis_url else 'Disabled'}")
    print(f"   Email Service: {settings.email_service}")
    print(f"   CORS Origins: {', '.join(settings.get_cors_origins_list())}")
    print(f"   Strict Production Mode: {'Enabled' if settings.full_production_configuration else 'Disabled'}")
    if settings.is_sentry_available():
        print(f"   Sentry: Enabled")

    return {
        "status": "success",
        "environment": settings.environment,
        "app_name": settings.app_name,
        "database": settings.db_name,
        "strict_mode": settings.full_production_configuration,
    }


# ============================================
# TEST UTILITIES
# ============================================

def test_configuration() -> None:
    """
    Test configuration loading and display all settings.
    Run with: python -m backend.config
    """
    print("\n" + "=" * 70)
    print("CRYPTOVAULT CONFIGURATION TEST")
    print("=" * 70)

    print("\nApplication:")
    print(f"  Name: {settings.app_name}")
    print(f"  Version: {settings.app_version}")
    print(f"  Environment: {settings.environment}")
    print(f"  Debug: {settings.debug}")
    print(f"  Frontend URL: {settings.app_url}")

    print("\nServer:")
    print(f"  Host: {settings.host}")
    print(f"  Port: {settings.port}")
    print(f"  Workers: {settings.workers}")

    print("\nDatabase (MongoDB):")
    print(f"  URL: {settings.mongo_url[:60]}...")
    print(f"  Database: {settings.db_name}")
    print(f"  Max Pool Size: {settings.mongo_max_pool_size}")
    print(f"  Timeout: {settings.mongo_timeout_ms}ms")

    print("\nCache (Redis):")
    if settings.use_redis:
        if settings.upstash_redis_rest_url:
            print(f"  Provider: Upstash REST API")
            print(f"  URL: {settings.upstash_redis_rest_url[:60]}...")
        elif settings.redis_url:
            print(f"  Provider: Standard Redis")
            print(f"  URL: {settings.redis_url[:60]}...")
        else:
            print(f"  Status: Redis disabled (use_redis=false)")
    else:
        print(f"  Status: Redis disabled")
    print(f"  Prefix: {settings.redis_prefix}")

    print("\nSecurity:")
    print(f"  JWT Algorithm: {settings.jwt_algorithm}")
    print(f"  JWT Secret: {'✓ Set' if settings.jwt_secret else '✗ Not set'}")
    print(f"  Access Token Expiry: {settings.access_token_expire_minutes} minutes")
    print(f"  Refresh Token Expiry: {settings.refresh_token_expire_days} days")
    print(f"  CSRF Secret: {'✓ Set' if settings.csrf_secret else '✗ Not set'}")

    print("\nCORS:")
    print(f"  Origins: {', '.join(settings.get_cors_origins_list())}")

    print("\nEmail:")
    print(f"  Service: {settings.email_service}")
    print(f"  From: {settings.email_from}")
    print(f"  From Name: {settings.email_from_name}")
    print(f"  Verification URL: {settings.email_verification_url}")
    if settings.sendgrid_api_key:
        print(f"  SendGrid: ✓ Configured")
    if settings.resend_api_key:
        print(f"  Resend: ✓ Configured")

    print("\nExternal Services:")
    print(f"  CoinCap API: {'✓ Configured' if settings.coincap_api_key else '✗ Not configured'}")
    print(f"  NowPayments: {'✓ Configured' if settings.nowpayments_api_key else '✗ Not configured'}")
    print(f"  Firebase: {'✓ Configured' if (settings.firebase_credentials_path or settings.firebase_credential) else '✗ Not configured'}")
    print(f"  Mock Prices: {settings.use_mock_prices}")

    print("\nRate Limiting:")
    print(f"  Requests/Minute: {settings.rate_limit_per_minute}")

    print("\nMonitoring:")
    print(f"  Sentry: {'✓ Enabled' if settings.is_sentry_available() else '✗ Disabled'}")
    if settings.is_sentry_available():
        print(f"  Traces Sample Rate: {settings.sentry_traces_sample_rate}")
        print(f"  Profiles Sample Rate: {settings.sentry_profiles_sample_rate}")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    test_configuration()
