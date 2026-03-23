"""Authentication and user management endpoints."""

from fastapi import APIRouter, HTTPException, Request, Response, status, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import uuid
import bcrypt
from typing import Optional
import logging
import asyncio
import re

from models import (
    User, UserCreate, UserLogin, UserResponse,
    VerifyEmailRequest, ResendVerificationRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    TwoFactorSetup, TwoFactorVerify, BackupCodes
)
from config import settings
from email_service import (
    email_service,
    generate_verification_code,
    generate_verification_token,
    generate_password_reset_token,
    get_token_expiration
)
from auth import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token,
    decode_token, generate_backup_codes, generate_2fa_secret,
    generate_device_fingerprint, verify_2fa_code, get_token_jti
)
from referral_service import ReferralService
from dependencies import get_current_user_id, get_db
from blacklist import blacklist_token, is_token_blacklisted
from redis_cache import redis_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])

PASSWORD_POLICY_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$")


def validate_password_policy(password: str) -> None:
    """Server-side password policy enforcement to match signup/reset flows."""
    if not PASSWORD_POLICY_REGEX.match(password or ""):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be 8-128 characters and include at least "
                "one uppercase letter, one lowercase letter, and one number."
            ),
        )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    Set authentication cookies with proper SameSite and Secure attributes.
    H5 FIX: Unified cookie security logic.
    """
    same_site = "none" if settings.use_cross_site_cookies else "lax"
    secure = True  # Always Secure - preview and production both use HTTPS

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        max_age=settings.access_token_expire_minutes * 60,
        path="/"
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/"
    )


async def log_audit(
    db, user_id: str, action: str, 
    resource: Optional[str] = None,
    ip_address: Optional[str] = None, 
    details: Optional[dict] = None,
    request_id: Optional[str] = None
):
    """Log audit event."""
    from models import AuditLog
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"Audit log: {action}",
        extra={
            "type": "audit_log",
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "ip_address": ip_address,
            "request_id": request_id
        }
    )
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        ip_address=ip_address,
        details=details
    )
    await db.get_collection("audit_logs").insert_one(audit_log.dict())


@router.post("/signup")
async def signup(
    user_data: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """Create a new user account with KYC data collection and non-blocking email"""
    users_collection = db.get_collection("users")
    portfolios_collection = db.get_collection("portfolios")
    wallets_collection = db.get_collection("wallets")

    referral_service = ReferralService(db)

    existing_user = await users_collection.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    validate_password_policy(user_data.password)

    verification_code = generate_verification_code()
    verification_token = generate_verification_token()
    verification_expires = get_token_expiration(hours=24)
    
    # Collect fraud detection data
    from services.fraud_detection import fraud_detection
    fraud_data = fraud_detection.collect_fraud_data(
        request,
        fingerprint_data={
            'fingerprint': user_data.device_fingerprint,
            'screen_info': user_data.screen_info
        } if user_data.device_fingerprint else None
    )

    # Auto-verify email when email service is mocked (for development/testing)
    auto_verify = settings.environment != 'production' and settings.email_service == 'mock'
    
    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=get_password_hash(user_data.password),
        email_verified=auto_verify,  # Auto-verify when email is mocked
        email_verification_code=verification_code,
        email_verification_token=verification_token,
        email_verification_expires=verification_expires,
        
        # KYC fields
        full_name=user_data.full_name,
        date_of_birth=user_data.date_of_birth,
        phone_number=user_data.phone_number,
        country=user_data.country,
        address=user_data.address,
        city=user_data.city,
        postal_code=user_data.postal_code,
        occupation=user_data.occupation,
        kyc_status='pending',
        kyc_tier=0,
        
        # Fraud detection data
        signup_ip=fraud_data['ip_address'],
        signup_is_proxied=fraud_data['is_proxied'],
        signup_device_fingerprint=fraud_data.get('device_fingerprint'),
        signup_user_agent=fraud_data['user_agent'],
        signup_screen_info=fraud_data.get('screen_info'),
        fraud_risk_score=fraud_data['risk_score'],
        fraud_risk_level=fraud_data['risk_level']
    )

    referral_code_input = referral_service.normalize_referral_code(user_data.referral_code or "")
    referral_validation = None
    if referral_code_input:
        referral_validation = await referral_service.validate_referral_code(user.id, referral_code_input)
        if not referral_validation.get("success"):
            raise HTTPException(status_code=400, detail=referral_validation.get("error", "Invalid referral code"))

    await users_collection.insert_one(user.dict())

    from models import Portfolio, Wallet
    portfolio = Portfolio(user_id=user.id)
    await portfolios_collection.insert_one(portfolio.dict())
    
    wallet = Wallet(user_id=user.id, balances={"USD": 0.0})
    await wallets_collection.insert_one(wallet.dict())

    referral_result = None
    if referral_code_input:
        referral_result = await referral_service.apply_referral_code(
            user.id,
            referral_code_input,
            validation=referral_validation,
        )

    generated_referral_code = await referral_service.get_or_create_referral_code(user.id)

    # FIX #2: Send verification email asynchronously to prevent blocking signup
    # Email service can take up to 60 seconds, which exceeds frontend 15s timeout
    # Move email sending to background task to complete signup immediately
    async def send_verification_email_background():
        """Background task to send verification email without blocking signup response"""
        try:
            app_url = settings.app_url
            subject, html_content, text_content = email_service.get_verification_email(
                name=user.name,
                code=verification_code,
                token=verification_token,
                app_url=app_url
            )
            
            email_sent = await email_service.send_email(
                to_email=user.email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            if email_sent:
                logger.info(f"✅ Verification email sent successfully to {user.email}")
            else:
                logger.warning(f"⚠️ Failed to send verification email to {user.email}")
        except Exception as e:
            logger.error(f"❌ Error sending verification email to {user.email}: {str(e)}")
    
    # Add email sending to background tasks (non-blocking)
    background_tasks.add_task(send_verification_email_background)

    await log_audit(
        db, user.id, "USER_SIGNUP",
        ip_address=request.client.host,
        request_id=getattr(request.state, "request_id", "unknown")
    )
    
    # Notify admin via Telegram (if KYC info provided) - also in background
    if user_data.full_name and user_data.date_of_birth:
        async def send_telegram_notification():
            try:
                from services.telegram_bot import telegram_bot
                user_dict = user.dict()
                user_dict.update(fraud_data)  # Add fraud data for admin
                await telegram_bot.notify_new_kyc_submission(user.id, user_dict)
                logger.info(f"✅ Telegram notification sent for new user: {user.id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send Telegram notification: {str(e)}")
        
        background_tasks.add_task(send_telegram_notification)

    response_data = {
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            createdAt=user.created_at.isoformat()
        ).dict(),
        "message": "Account created!" if auto_verify else "Account created! Please check your email to verify your account.",
        "emailSent": True,  # Always return True since email is sent in background
        "verificationRequired": not auto_verify,  # Skip verification in mock mode
        "kyc_status": user.kyc_status,
        "referralApplied": bool(referral_result and referral_result.get("success")),
        "ownReferralCode": generated_referral_code
    }
    
    # Auto-login user if email verification not required (dev/mock mode)
    if auto_verify:
        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        response_data["access_token"] = access_token
        
        response = JSONResponse(content=response_data)
        set_auth_cookies(response, access_token, refresh_token)
        logger.info(f"Auto-login after signup for user: {user.id}")
        return response
    
    return response_data


@router.post("/login")
async def login(
    credentials: UserLogin,
    request: Request,
    db = Depends(get_db)
):
    """Login user with account lockout protection and database timeout handling."""
    users_collection = db.get_collection("users")

    # FIX #1: Add timeout handling to prevent infinite loading spinner
    # Wrap database operations with timeout to prevent indefinite hangs
    DB_QUERY_TIMEOUT = 10  # 10 seconds max for database queries
    
    try:
        # Query user with timeout
        user_doc = await asyncio.wait_for(
            users_collection.find_one({"email": credentials.email}),
            timeout=DB_QUERY_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"Database query timeout during login for email: {credentials.email}")
        raise HTTPException(
            status_code=504,
            detail="Login request timed out. Please try again."
        )
    except Exception as e:
        logger.error(f"Database error during login: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred during login. Please try again."
        )
    
    if not user_doc:
        verify_password("dummy_password", bcrypt.gensalt().decode())
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = User(**user_doc)

    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        # H3 FIX: Use generic error to prevent account state enumeration
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    device_fingerprint = generate_device_fingerprint(request)
    login_attempt = {
        "id": str(uuid.uuid4()),
        "user_id": user.id,
        "email": credentials.email,
        "ip_address": request.client.host,
        "device_fingerprint": device_fingerprint,
        "timestamp": datetime.now(timezone.utc),
        "success": False
    }
    if not verify_password(credentials.password, user.password_hash):
        failed_attempts = user.failed_login_attempts + 1
        update_data = {
            "failed_login_attempts": failed_attempts,
            "last_failed_attempt": datetime.now(timezone.utc)
        }
        
        if failed_attempts >= 5:
            update_data["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=15)
            try:
                await asyncio.wait_for(
                    users_collection.update_one({"id": user.id}, {"$set": update_data}),
                    timeout=DB_QUERY_TIMEOUT
                )
                await asyncio.wait_for(
                    db.get_collection("login_attempts").insert_one(login_attempt),
                    timeout=DB_QUERY_TIMEOUT
                )
                await asyncio.wait_for(
                    log_audit(db, user.id, "ACCOUNT_LOCKED", ip_address=request.client.host),
                    timeout=DB_QUERY_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.error(f"Database timeout during failed login attempt for user: {user.id}")
            # H3 FIX: Generic error to prevent enumeration
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        try:
            await asyncio.wait_for(
                users_collection.update_one({"id": user.id}, {"$set": update_data}),
                timeout=DB_QUERY_TIMEOUT
            )
            await asyncio.wait_for(
                db.get_collection("login_attempts").insert_one(login_attempt),
                timeout=DB_QUERY_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Database timeout during failed login attempt for user: {user.id}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Skip email verification check in non-production environments
    skip_verification = (
        settings.environment != 'production'
    )
    if not user.email_verified and not skip_verification:
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Email verification required before login.",
                "code": "EMAIL_NOT_VERIFIED",
                "verificationRequired": True,
                "nextAction": "verify_email"
            }
        )

    try:
        # Update user login status with timeout
        await asyncio.wait_for(
            users_collection.update_one(
                {"id": user.id},
                {"$set": {
                    "failed_login_attempts": 0,
                    "locked_until": None,
                    "last_login": datetime.now(timezone.utc)
                }}
            ),
            timeout=DB_QUERY_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"Database timeout updating login status for user: {user.id}")
        # Continue with login even if update fails

    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    try:
        await asyncio.wait_for(
            log_audit(db, user.id, "USER_LOGIN", ip_address=request.client.host),
            timeout=DB_QUERY_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"Database timeout logging audit for user: {user.id}")
        # Continue with login even if audit log fails

    logger.info(f"Setting cookies - access_token length: {len(access_token)}, refresh_token length: {len(refresh_token)}")

    response = JSONResponse(content={
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            createdAt=user.created_at.isoformat()
        ).dict(),
        "access_token": access_token
    })
    
    # Set auth cookies with proper SameSite and Secure attributes
    set_auth_cookies(response, access_token, refresh_token)
    
    logger.info(f"Response headers: {dict(response.headers)}")
    return response


@router.post("/logout")
async def logout(
    request: Request, 
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Secure logout: Blacklist tokens from both cookies and Authorization header, then delete cookies."""
    refresh_token = request.cookies.get("refresh_token")
    access_token = request.cookies.get("access_token")

    # Also check Authorization header for Bearer token
    auth_header = request.headers.get("Authorization", "")
    bearer_token = None
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:]

    # Blacklist all tokens found
    tokens_to_blacklist = set()
    if refresh_token:
        tokens_to_blacklist.add(("refresh", refresh_token))
    if access_token:
        tokens_to_blacklist.add(("access", access_token))
    if bearer_token and bearer_token != access_token:
        tokens_to_blacklist.add(("access", bearer_token))

    for token_type, token_val in tokens_to_blacklist:
        payload = decode_token(token_val, expected_type=token_type)
        if payload:
            expires_in = int(payload["exp"] - datetime.now(timezone.utc).timestamp())
            await blacklist_token(token_val, max(expires_in, 60))

    await log_audit(db, user_id, "USER_LOGOUT", ip_address=request.client.host)

    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.get("/me")
async def get_current_user_profile(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get current user profile."""
    users_collection = db.get_collection("users")
    user_doc = await users_collection.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    user = User(**user_doc)
    return {
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            createdAt=user.created_at.isoformat()
        ).dict()
    }


@router.put("/profile")
async def update_profile(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Update user profile."""
    users_collection = db.get_collection("users")
    body = await request.json()
    name = body.get("name")
    if not name or len(name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters")
    await users_collection.update_one(
        {"id": user_id},
        {"$set": {"name": name.strip()}}
    )
    user_doc = await users_collection.find_one({"id": user_id})
    user = User(**user_doc)
    await log_audit(db, user_id, "PROFILE_UPDATED", ip_address=request.client.host)
    return {
        "message": "Profile updated successfully",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            createdAt=user.created_at.isoformat()
        ).dict()
    }


@router.post("/change-password")
async def change_password(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Change user password and invalidate all existing sessions (H2 fix)."""
    users_collection = db.get_collection("users")
    body = await request.json()
    current_password = body.get("current_password")
    new_password = body.get("new_password")
    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Current and new password are required")
    validate_password_policy(new_password)
    user_doc = await users_collection.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    user = User(**user_doc)
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    new_hashed_password = get_password_hash(new_password)

    # H2 FIX: Store password_changed_at to invalidate all existing tokens
    await users_collection.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": new_hashed_password,
            "password_changed_at": datetime.now(timezone.utc),
        }}
    )
    await log_audit(db, user_id, "PASSWORD_CHANGED", ip_address=request.client.host)

    # Issue fresh tokens for this session only
    access_token = create_access_token(data={"sub": user_id})
    refresh_token_val = create_refresh_token(data={"sub": user_id})

    response = JSONResponse(content={"message": "Password changed successfully. All other sessions have been logged out."})
    set_auth_cookies(response, access_token, refresh_token_val)
    return response


@router.post("/refresh")
async def refresh_token(request: Request):
    """Refresh access token with token rotation (H1 fix)."""
    old_refresh_token = request.cookies.get("refresh_token")
    if not old_refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    # Check if the incoming refresh token has been blacklisted (replay protection)
    if await is_token_blacklisted(old_refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    payload = decode_token(old_refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # H1 FIX: Rotate refresh token - issue both new access AND new refresh tokens
    new_access_token = create_access_token(data={"sub": user_id})
    new_refresh_token = create_refresh_token(data={"sub": user_id})

    # Blacklist the old refresh token to prevent reuse
    old_exp = payload.get("exp", 0)
    expires_in = max(int(old_exp - datetime.now(timezone.utc).timestamp()), 60)
    await blacklist_token(old_refresh_token, expires_in)

    response = JSONResponse(content={"message": "Token refreshed"})
    set_auth_cookies(response, new_access_token, new_refresh_token)
    return response


@router.post("/verify-email")
async def verify_email(
    data: VerifyEmailRequest, 
    request: Request,
    db = Depends(get_db)
):
    """Verify email with code or token."""
    users_collection = db.get_collection("users")

    user_doc = await users_collection.find_one({
        "$or": [
            {"email_verification_code": data.token},
            {"email_verification_token": data.token}
        ]
    })

    if not user_doc:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    user = User(**user_doc)

    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    if user.email_verification_expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Verification code expired. Please request a new one."
        )

    await users_collection.update_one(
        {"id": user.id},
        {"$set": {
            "email_verified": True,
            "email_verification_code": None,
            "email_verification_token": None,
            "email_verification_expires": None
        }}
    )

    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    await log_audit(db, user.id, "EMAIL_VERIFIED")

    subject, html_content, text_content = email_service.get_welcome_email(
        name=user.name,
        app_url=settings.app_url
    )
    await email_service.send_email(
        to_email=user.email,
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )

    response = JSONResponse(content={
        "message": "Email verified successfully!",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            createdAt=user.created_at.isoformat()
        ).dict()
    })

    # Set auth cookies with proper SameSite and Secure attributes
    set_auth_cookies(response, access_token, refresh_token)

    return response


@router.post("/resend-verification")
async def resend_verification(
    data: ResendVerificationRequest, 
    request: Request,
    db = Depends(get_db)
):
    """Resend verification email."""
    users_collection = db.get_collection("users")

    user_doc = await users_collection.find_one({"email": data.email})
    if not user_doc:
        return {"message": "If this email is registered, a verification email has been sent."}

    user = User(**user_doc)

    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    verification_code = generate_verification_code()
    verification_token = generate_verification_token()
    verification_expires = get_token_expiration(hours=24)

    await users_collection.update_one(
        {"id": user.id},
        {"$set": {
            "email_verification_code": verification_code,
            "email_verification_token": verification_token,
            "email_verification_expires": verification_expires
        }}
    )

    subject, html_content, text_content = email_service.get_verification_email(
        name=user.name,
        code=verification_code,
        token=verification_token,
        app_url=settings.app_url
    )

    await email_service.send_email(
        to_email=user.email,
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )

    return {"message": "Verification email sent! Please check your inbox."}


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest, 
    request: Request,
    db = Depends(get_db)
):
    """Request password reset email."""
    users_collection = db.get_collection("users")

    client_ip = (request.client.host if request.client else "unknown").lower()
    email_key = data.email.strip().lower()

    # Layered throttling (IP + email) to reduce abuse and email flooding.
    ip_allowed = await redis_cache.rate_limit_check(
        f"auth:forgot-password:ip:{client_ip}",
        limit=20,
        window=60,
    )
    email_allowed = await redis_cache.rate_limit_check(
        f"auth:forgot-password:email:{email_key}",
        limit=5,
        window=3600,
    )
    if not ip_allowed or not email_allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many password reset requests. Please try again later.",
        )

    user_doc = await users_collection.find_one({"email": data.email})

    if not user_doc:
        return {"message": "If this email is registered, a password reset link has been sent."}

    user = User(**user_doc)

    reset_token = generate_password_reset_token()
    reset_expires = get_token_expiration(hours=1)

    await users_collection.update_one(
        {"id": user.id},
        {"$set": {
            "password_reset_token": reset_token,
            "password_reset_expires": reset_expires
        }}
    )

    subject, html_content, text_content = email_service.get_password_reset_email(
        name=user.name,
        token=reset_token,
        app_url=settings.app_url
    )

    await email_service.send_email(
        to_email=user.email,
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )

    await log_audit(db, user.id, "PASSWORD_RESET_REQUESTED")

    return {"message": "If this email is registered, a password reset link has been sent."}


@router.get("/validate-reset-token/{token}")
async def validate_reset_token(token: str, db = Depends(get_db)):
    """Validate if password reset token is valid."""
    users_collection = db.get_collection("users")

    user_doc = await users_collection.find_one({"password_reset_token": token})

    if not user_doc:
        return {"valid": False, "message": "Invalid reset token"}

    user = User(**user_doc)

    if user.password_reset_expires < datetime.now(timezone.utc):
        return {"valid": False, "message": "Reset token expired"}

    return {"valid": True, "message": "Token is valid"}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest, 
    request: Request,
    db = Depends(get_db)
):
    """Reset password with valid token."""
    users_collection = db.get_collection("users")

    user_doc = await users_collection.find_one({"password_reset_token": data.token})

    if not user_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = User(**user_doc)

    if user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token expired. Please request a new one.")

    validate_password_policy(data.new_password)

    new_password_hash = get_password_hash(data.new_password)

    await users_collection.update_one(
        {"id": user.id},
        {"$set": {
            "password_hash": new_password_hash,
            "password_reset_token": None,
            "password_reset_expires": None,
            "failed_login_attempts": 0,
            "locked_until": None
        }}
    )

    await log_audit(db, user.id, "PASSWORD_RESET_COMPLETED")

    return {"message": "Password reset successfully! You can now log in with your new password."}


# 2FA Endpoints
@router.post("/2fa/setup")
async def setup_2fa(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Setup 2FA for user."""
    users_collection = db.get_collection("users")
    secret = generate_2fa_secret()

    await users_collection.update_one(
        {"id": user_id},
        {"$set": {"two_factor_secret": secret}}
    )

    otp_auth_url = f"otpauth://totp/CryptoVault:{user_id}?secret={secret}&issuer=CryptoVault"
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?data={quote_plus(otp_auth_url)}&size=200x200"

    return {
        "secret": secret,
        "qr_code_url": otp_auth_url,  # Backward compatibility
        "otp_auth_url": otp_auth_url,
        "qrCode": qr_image_url,
        "backupCodes": []
    }


@router.post("/2fa/verify")
async def verify_2fa(
    data: TwoFactorVerify, 
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Verify 2FA code and enable 2FA if valid."""
    users_collection = db.get_collection("users")

    if len(data.code) != 6 or not data.code.isdigit():
        raise HTTPException(status_code=400, detail="Invalid code format")

    # Get user to retrieve the 2FA secret
    user_doc = await users_collection.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    # Check if 2FA secret exists
    secret = user_doc.get("two_factor_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="2FA setup not initiated. Please setup 2FA first.")
    # Verify the TOTP code
    if not verify_2fa_code(secret, data.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Generate backup codes and enable 2FA
    backup_codes = generate_backup_codes()
    await users_collection.update_one(
        {"id": user_id},
        {"$set": {
            "two_factor_enabled": True,
            "backup_codes": backup_codes
        }}
    )

    return {
        "message": "2FA enabled successfully",
        "backup_codes": backup_codes,
        "backupCodes": backup_codes
    }


@router.get("/2fa/status")
async def get_2fa_status(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get 2FA status."""
    users_collection = db.get_collection("users")
    user_doc = await users_collection.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    return {"enabled": user_doc.get("two_factor_enabled", False)}


@router.post("/2fa/disable")
async def disable_2fa(
    data: dict, 
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Disable 2FA."""
    users_collection = db.get_collection("users")
    await users_collection.update_one(
        {"id": user_id},
        {"$set": {
            "two_factor_enabled": False,
            "two_factor_secret": None,
            "backup_codes": []
        }}
    )

    return {"message": "2FA disabled successfully"}


@router.post("/2fa/backup-codes")
async def get_backup_codes(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Generate new backup codes."""
    users_collection = db.get_collection("users")
    backup_codes = generate_backup_codes()
    await users_collection.update_one(
        {"id": user_id},
        {"$set": {"backup_codes": backup_codes}}
    )

    return {"codes": backup_codes, "backupCodes": backup_codes}
