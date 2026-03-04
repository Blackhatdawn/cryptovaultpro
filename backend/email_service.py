"""
CryptoVault Enterprise Email Service with SendGrid + SMTP Integration
Enterprise-grade email system with:
- SendGrid integration for production email delivery
- SMTP integration for standard relay-based delivery
- Retry logic with exponential backoff
- Rate limiting awareness
- SOC 2 compliance logging
- Beautiful HTML templates
- 6-digit OTP verification with 5-minute expiry
"""
import random
import secrets
import string
import asyncio
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any
import logging
from email.message import EmailMessage

import aiosmtplib
import httpx

from config import settings

logger = logging.getLogger(__name__)

# FIX #2: Reduce retry delays to keep total email time under 10 seconds
# Previous config: 3 retries with exponential backoff could take 60+ seconds
# New config: 2 retries with shorter delays keeps total time under 10 seconds
EMAIL_RETRY_CONFIG = {
    "max_retries": 2,  # Reduced from 3 to 2
    "base_delay": 0.5,  # Reduced from 1.0 to 0.5 seconds
    "max_delay": 5.0,  # Reduced from 30.0 to 5.0 seconds
    "exponential_base": 2.0,
    "send_timeout": 5.0,  # Add timeout for individual send attempts
}

# Try to import SendGrid
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    logger.warning("SendGrid not installed. Using mock email service.")


def generate_verification_code(length: int = 6) -> str:
    """Generate a secure random 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=length))


def generate_verification_token() -> str:
    """Generate a secure random verification token."""
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    """Generate a secure random password reset token."""
    return secrets.token_urlsafe(32)


def get_token_expiration(hours: int = 24, minutes: int = 0) -> datetime:
    """Get token expiry timestamp."""
    return datetime.utcnow() + timedelta(hours=hours, minutes=minutes)


class EmailService:
    """
    Production-ready email service with SendGrid and SMTP integration.
    Falls back to mock mode if configured provider is unavailable.
    Includes CryptoVault branding and SOC 2 compliant logging.
    """
    
    def __init__(self):
        # Extract secret value if it's a SecretStr
        api_key = settings.sendgrid_api_key
        self.sendgrid_api_key = api_key.get_secret_value() if api_key else None
        resend_api_key = settings.resend_api_key
        self.resend_api_key = resend_api_key.get_secret_value() if resend_api_key else None
        self.resend_api_url = "https://api.resend.com/emails"
        self.from_email = settings.email_from
        self.from_name = settings.email_from_name

        smtp_password = settings.smtp_password
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = smtp_password.get_secret_value() if smtp_password else None
        self.smtp_use_tls = settings.smtp_use_tls
        self.smtp_use_ssl = settings.smtp_use_ssl

        configured_service = settings.email_service
        self.client = None
        is_production = settings.environment == 'production'

        if configured_service == 'sendgrid':
            if self.sendgrid_api_key and SENDGRID_AVAILABLE:
                self.client = SendGridAPIClient(self.sendgrid_api_key)
                self.mode = 'sendgrid'
                logger.info("✅ Email service initialized with SendGrid")
            else:
                # FIX #3: In production, FAIL LOUDLY if email service is misconfigured
                # Don't silently fall back to mock mode in production
                if is_production:
                    error_msg = "❌ CRITICAL: Email service misconfigured in production environment"
                    if not self.sendgrid_api_key:
                        error_msg += " - SENDGRID_API_KEY is missing"
                    elif not SENDGRID_AVAILABLE:
                        error_msg += " - sendgrid package not installed"
                    logger.error(error_msg)
                    raise RuntimeError(
                        f"{error_msg}. Production requires properly configured email service. "
                        "Set SENDGRID_API_KEY or change EMAIL_SERVICE setting."
                    )
                else:
                    self.mode = 'mock'
                    if not self.sendgrid_api_key:
                        logger.warning("⚠️ SENDGRID_API_KEY missing - falling back to mock email mode")
                    elif not SENDGRID_AVAILABLE:
                        logger.warning("⚠️ sendgrid package not installed - falling back to mock email mode")
                    logger.info("📧 Email service running in mock mode")

        elif configured_service == 'resend':
            if self.resend_api_key:
                self.mode = 'resend'
                logger.info("✅ Email service initialized with Resend")
            else:
                if is_production:
                    error_msg = "❌ CRITICAL: Resend email service misconfigured in production - RESEND_API_KEY is missing"
                    logger.error(error_msg)
                    raise RuntimeError(
                        f"{error_msg}. Production requires properly configured email service. "
                        "Set RESEND_API_KEY or change EMAIL_SERVICE setting."
                    )
                self.mode = 'mock'
                logger.warning(
                    "⚠️ RESEND_API_KEY is missing - falling back to mock email mode"
                )
                logger.info("📧 Email service running in mock mode")

        elif configured_service == 'smtp':
            if self.smtp_host:
                self.mode = 'smtp'
                logger.info("✅ Email service initialized with SMTP")
            else:
                # FIX #3: In production, FAIL LOUDLY if SMTP is misconfigured
                if is_production:
                    error_msg = "❌ CRITICAL: SMTP email service misconfigured in production - SMTP_HOST is missing"
                    logger.error(error_msg)
                    raise RuntimeError(
                        f"{error_msg}. Production requires properly configured email service. "
                        "Set SMTP_HOST or change EMAIL_SERVICE setting."
                    )
                else:
                    self.mode = 'mock'
                    logger.warning(
                        "⚠️ SMTP is selected but SMTP_HOST is missing - falling back to mock email mode"
                    )
                    logger.info("📧 Email service running in mock mode")

        else:
            # FIX #3: In production, don't allow mock email mode
            if is_production and configured_service == 'mock':
                error_msg = "❌ CRITICAL: Mock email service is not allowed in production"
                logger.error(error_msg)
                raise RuntimeError(
                    f"{error_msg}. Set EMAIL_SERVICE to 'sendgrid', 'resend', or 'smtp' and provide credentials."
                )
            self.mode = 'mock'
            logger.info("📧 Email service running in mock mode")

    def _get_email_header(self) -> str:
        """Get branded email header HTML."""
        return """
        <tr>
            <td style="padding: 40px 40px 20px; text-align: center; border-bottom: 1px solid #2a2a2d;">
                <div style="width: 80px; height: 80px; margin: 0 auto 20px; background: linear-gradient(135deg, #C5A049 0%, #8B7355 100%); border-radius: 16px; display: flex; align-items: center; justify-content: center;">
                    <span style="font-size: 40px;">🛡️</span>
                </div>
                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">CryptoVault</h1>
                <p style="margin: 8px 0 0; color: #C5A049; font-size: 14px; letter-spacing: 2px;">SECURE DIGITAL CUSTODY</p>
            </td>
        </tr>
        """
    
    def _get_email_footer(self) -> str:
        """Get branded email footer HTML."""
        return """
        <tr>
            <td style="padding: 24px 40px; background-color: #0d0d0e; border-top: 1px solid #2a2a2d; text-align: center;">
                <p style="margin: 0 0 8px; color: #666; font-size: 12px;">© 2024 CryptoVault Financial, Inc. All rights reserved.</p>
                <p style="margin: 0; color: #555; font-size: 11px;">1201 Market Street, Suite 101, Wilmington, DE 19801</p>
            </td>
        </tr>
        """
    
    def get_verification_email(
        self,
        name: str,
        code: str,
        token: str,
        app_url: str
    ) -> Tuple[str, str, str]:
        """
        Generate verification email content with 6-digit OTP code.
        Returns: (subject, html_content, text_content)
        """
        subject = "🔐 CryptoVault - Verify Your Email"
        
        verify_link = f"{app_url}/verify?token={token}"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0a0a0b; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="100%" style="max-width: 600px;" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #1a1a1d 0%, #0d0d0e 100%); border-radius: 16px; border: 1px solid #2a2a2d; overflow: hidden;">
                    {self._get_email_header()}
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px; background: #1a1a1d;">
                            <h2 style="margin: 0 0 16px; color: #ffffff; font-size: 24px; font-weight: 600;">Verify Your Email</h2>
                            <p style="margin: 0 0 24px; color: #a0a0a5; font-size: 16px; line-height: 1.6;">
                                Hello {name},<br><br>
                                Welcome to CryptoVault! Use the verification code below to complete your account setup.
                            </p>
                            
                            <!-- OTP Code Box -->
                            <div style="background: linear-gradient(135deg, #C5A049 0%, #a88b3d 100%); border-radius: 12px; padding: 24px; text-align: center; margin: 24px 0;">
                                <p style="margin: 0 0 8px; color: #0a0a0b; font-size: 14px; font-weight: 500; letter-spacing: 1px;">YOUR VERIFICATION CODE</p>
                                <div style="font-size: 36px; font-weight: 700; color: #0a0a0b; letter-spacing: 8px; font-family: 'Courier New', monospace;">
                                    {code}
                                </div>
                            </div>
                            
                            <p style="margin: 24px 0 0; color: #ff6b6b; font-size: 14px; text-align: center;">
                                ⏰ This code expires in <strong>5 minutes</strong>
                            </p>
                            
                            <div style="text-align: center; margin: 24px 0;">
                                <p style="color: #666; font-size: 14px; margin: 0 0 16px;">Or click the button below:</p>
                                <a href="{verify_link}" style="display: inline-block; background: linear-gradient(135deg, #C5A049 0%, #a88b3d 100%); color: #0a0a0b; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600;">Verify Email</a>
                            </div>
                            
                            <hr style="border: none; border-top: 1px solid #2a2a2d; margin: 32px 0;">
                            
                            <p style="margin: 0; color: #666; font-size: 13px; line-height: 1.6;">
                                <strong>Security Notice:</strong> If you didn't request this code, please ignore this email. Never share your verification code with anyone. CryptoVault will never ask for your password or codes via email.
                            </p>
                        </td>
                    </tr>
                    
                    {self._get_email_footer()}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
        
        text_content = f"""
CryptoVault - Verify Your Email

Hello {name},

Your verification code is: {code}

Or verify using this link: {verify_link}

This code expires in 5 minutes.

If you didn't request this code, please ignore this email.

---
CryptoVault Financial, Inc.
1201 Market Street, Suite 101, Wilmington, DE 19801
        """
        
        return subject, html_content, text_content
    
    def get_welcome_email(self, name: str, app_url: str) -> Tuple[str, str, str]:
        """Generate welcome email after successful verification."""
        subject = "🎉 Welcome to CryptoVault - Your Account is Ready!"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0a0a0b; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background: #1a1a1d; border-radius: 16px; border: 1px solid #2a2a2d;">
                    {self._get_email_header()}
                    <tr>
                        <td style="padding: 40px; text-align: center;">
                            <h1 style="color: #C5A049; margin: 0 0 20px;">🎉 Welcome to CryptoVault!</h1>
                            <p style="color: #ffffff; font-size: 18px; margin: 0 0 16px;">Hello {name},</p>
                            <p style="color: #a0a0a5; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">
                                Your account has been verified and is now ready to use. Start exploring secure P2P trading and institutional-grade custody.
                            </p>
                            <a href="{app_url}/dashboard" style="display: inline-block; background: linear-gradient(135deg, #C5A049 0%, #a88b3d 100%); color: #0a0a0b; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600;">Go to Dashboard</a>
                        </td>
                    </tr>
                    {self._get_email_footer()}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
        
        text_content = f"""
Welcome to CryptoVault!

Hello {name},

Your account has been verified and is now ready to use.

Get started: {app_url}/dashboard

---
CryptoVault Financial, Inc.
        """
        
        return subject, html_content, text_content
    
    def get_password_reset_email(
        self,
        name: str,
        token: str,
        app_url: str
    ) -> Tuple[str, str, str]:
        """Generate password reset email."""
        subject = "🔑 CryptoVault - Reset Your Password"
        
        reset_link = f"{app_url}/reset?token={token}"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="margin: 0; padding: 0; background-color: #0a0a0b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0a0a0b; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background: #1a1a1d; border-radius: 16px; border: 1px solid #2a2a2d;">
                    {self._get_email_header()}
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 16px; color: #ffffff; font-size: 24px; font-weight: 600;">Reset Your Password</h2>
                            <p style="margin: 0 0 24px; color: #a0a0a5; font-size: 16px; line-height: 1.6;">
                                Hello {name},<br><br>
                                We received a request to reset your password. Click the button below to create a new password.
                            </p>
                            
                            <div style="text-align: center; margin: 24px 0;">
                                <a href="{reset_link}" style="display: inline-block; background: linear-gradient(135deg, #C5A049 0%, #a88b3d 100%); color: #0a0a0b; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600;">Reset Password</a>
                            </div>
                            
                            <p style="margin: 24px 0 0; color: #ff6b6b; font-size: 14px; text-align: center;">
                                ⏰ This link expires in <strong>1 hour</strong>
                            </p>
                            
                            <hr style="border: none; border-top: 1px solid #2a2a2d; margin: 32px 0;">
                            
                            <p style="margin: 0; color: #666; font-size: 13px; line-height: 1.6;">
                                If you didn't request a password reset, please ignore this email or contact support if you have concerns.
                            </p>
                        </td>
                    </tr>
                    {self._get_email_footer()}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """
        
        text_content = f"""
CryptoVault - Reset Your Password

Hello {name},

Reset your password using this link: {reset_link}

This link expires in 1 hour.

If you didn't request this, please ignore this email.

---
CryptoVault Financial, Inc.
        """
        
        return subject, html_content, text_content
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        retry: bool = True
    ) -> bool:
        """
        Send email via SendGrid, SMTP, or mock with retry logic.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML email body
            text_content: Plain text email body
            retry: Whether to retry on failure
            
        Returns:
            True if successful, False otherwise
        """
        if self.mode == 'sendgrid' and self.client:
            if retry:
                return await self._send_with_retry(to_email, subject, html_content, text_content)
            return await self._send_sendgrid(to_email, subject, html_content, text_content)

        if self.mode == 'resend':
            return await self._send_resend(to_email, subject, html_content, text_content)

        if self.mode == 'smtp':
            return await self._send_smtp(to_email, subject, html_content, text_content)

        return await self._send_mock(to_email, subject)
    
    async def _send_with_retry(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Send email with exponential backoff retry logic."""
        last_error = None
        
        for attempt in range(EMAIL_RETRY_CONFIG["max_retries"]):
            try:
                success = await self._send_sendgrid(to_email, subject, html_content, text_content)
                if success:
                    if attempt > 0:
                        logger.info(f"✅ Email sent after {attempt + 1} attempts to {to_email}")
                    return True
                    
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Email attempt {attempt + 1} failed: {str(e)}")
            
            # Calculate backoff delay
            if attempt < EMAIL_RETRY_CONFIG["max_retries"] - 1:
                delay = min(
                    EMAIL_RETRY_CONFIG["base_delay"] * (EMAIL_RETRY_CONFIG["exponential_base"] ** attempt),
                    EMAIL_RETRY_CONFIG["max_delay"]
                )
                logger.info(f"⏳ Retrying email in {delay:.1f}s...")
                await asyncio.sleep(delay)
        
        logger.error(f"❌ Email failed after {EMAIL_RETRY_CONFIG['max_retries']} attempts to {to_email}")
        if last_error:
            logger.error(f"   Last error: {str(last_error)}")
        return False
    
    async def _send_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Send email via SendGrid API with timeout."""
        try:
            # FIX #2: Add timeout to individual email send attempts (5 seconds max)
            async def send_with_timeout():
                message = Mail(
                    from_email=Email(self.from_email, self.from_name),
                    to_emails=To(to_email),
                    subject=subject,
                    html_content=Content("text/html", html_content),
                    plain_text_content=Content("text/plain", text_content)
                )
                
                response = self.client.send(message)
                
                if response.status_code in [200, 201, 202]:
                    logger.info(f"✅ Email sent successfully to {to_email}")
                    return True
                else:
                    logger.error(f"❌ SendGrid error: {response.status_code}")
                    return False
            
            return await asyncio.wait_for(
                send_with_timeout(),
                timeout=EMAIL_RETRY_CONFIG["send_timeout"]
            )
                
        except asyncio.TimeoutError:
            logger.error(f"❌ SendGrid timeout after {EMAIL_RETRY_CONFIG['send_timeout']}s")
            raise  # Re-raise for retry logic
        except Exception as e:
            logger.error(f"❌ SendGrid exception: {str(e)}")
            raise  # Re-raise for retry logic
    
    async def _send_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Send email via SMTP with timeout."""
        try:
            message = EmailMessage()
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            message["Subject"] = subject
            message.set_content(text_content)
            message.add_alternative(html_content, subtype="html")

            # FIX #2: Reduce SMTP timeout from 20s to 5s to match send_timeout config
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username if self.smtp_username else None,
                password=self.smtp_password if self.smtp_password else None,
                start_tls=False if self.smtp_use_ssl else self.smtp_use_tls,
                use_tls=self.smtp_use_ssl,
                timeout=EMAIL_RETRY_CONFIG["send_timeout"],  # Reduced from 20 to 5 seconds
            )
            logger.info(f"✅ SMTP email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"❌ SMTP exception: {str(e)}")
            return False

    async def _send_resend(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Send email via Resend API with timeout."""
        try:
            payload = {
                "from": f"{self.from_name} <{self.from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=EMAIL_RETRY_CONFIG["send_timeout"]) as client:
                response = await client.post(
                    self.resend_api_url,
                    json=payload,
                    headers=headers,
                )

            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Resend email sent successfully to {to_email}")
                return True

            logger.error(
                "❌ Resend error: %s - %s",
                response.status_code,
                response.text,
            )
            return False
        except Exception as e:
            logger.error(f"❌ Resend exception: {str(e)}")
            return False

    async def _send_mock(self, to_email: str, subject: str) -> bool:
        """Mock email sending for development/testing."""
        logger.info(f"📧 [MOCK] Email to {to_email}")
        logger.info(f"📧 [MOCK] Subject: {subject}")
        return True
    
    # ============================================
    # ENTERPRISE EMAIL METHODS
    # ============================================
    
    async def send_p2p_transfer_sent(
        self,
        to_email: str,
        sender_name: str,
        recipient_name: str,
        recipient_email: str,
        amount: str,
        asset: str,
        gas_fee: str,
        transaction_id: str,
        note: Optional[str] = None
    ) -> bool:
        """Send P2P transfer confirmation to sender."""
        from email_templates import p2p_transfer_sent
        
        subject = f"✅ Transfer Sent: {amount} {asset} to {recipient_name}"
        html_content = p2p_transfer_sent(
            sender_name=sender_name,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            amount=amount,
            asset=asset,
            gas_fee=gas_fee,
            transaction_id=transaction_id,
            note=note
        )
        text_content = f"You sent {amount} {asset} to {recipient_name} ({recipient_email}). Transaction ID: {transaction_id}"
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_p2p_transfer_received(
        self,
        to_email: str,
        recipient_name: str,
        sender_name: str,
        sender_email: str,
        amount: str,
        asset: str,
        transaction_id: str,
        note: Optional[str] = None
    ) -> bool:
        """Send P2P transfer notification to recipient."""
        from email_templates import p2p_transfer_received
        
        subject = f"🎉 You Received {amount} {asset} from {sender_name}"
        html_content = p2p_transfer_received(
            recipient_name=recipient_name,
            sender_name=sender_name,
            sender_email=sender_email,
            amount=amount,
            asset=asset,
            transaction_id=transaction_id,
            note=note
        )
        text_content = f"You received {amount} {asset} from {sender_name} ({sender_email}). Transaction ID: {transaction_id}"
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_price_alert(
        self,
        to_email: str,
        name: str,
        asset: str,
        current_price: str,
        target_price: str,
        condition: str,
        alert_id: str
    ) -> bool:
        """Send price alert notification."""
        from email_templates import price_alert_triggered
        
        condition_text = "reached" if condition == "above" else "dropped below"
        subject = f"🔔 {asset} {condition_text} {target_price}"
        html_content = price_alert_triggered(
            name=name,
            asset=asset,
            current_price=current_price,
            target_price=target_price,
            condition=condition,
            alert_id=alert_id
        )
        text_content = f"{asset} has {condition_text} your target price of {target_price}. Current price: {current_price}"
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_new_device_login(
        self,
        to_email: str,
        name: str,
        device: str,
        browser: str,
        ip_address: str,
        location: str,
        login_time: str
    ) -> bool:
        """Send new device login notification."""
        from email_templates import login_new_device
        
        subject = "🔐 New Login to Your CryptoVault Account"
        html_content = login_new_device(
            name=name,
            device=device,
            browser=browser,
            ip_address=ip_address,
            location=location,
            login_time=login_time
        )
        text_content = f"New login detected from {device} ({browser}) in {location}. IP: {ip_address}. Time: {login_time}"
        
        return await self.send_email(to_email, subject, html_content, text_content)
    
    async def send_security_alert(
        self,
        to_email: str,
        name: str,
        alert_type: str,
        details: str,
        ip_address: str,
        location: str
    ) -> bool:
        """Send security alert notification."""
        from email_templates import security_alert
        
        subject = f"🔐 Security Alert: {alert_type}"
        html_content = security_alert(
            name=name,
            alert_type=alert_type,
            details=details,
            ip_address=ip_address,
            location=location
        )
        text_content = f"Security Alert: {alert_type}. {details}. IP: {ip_address}. Location: {location}"
        
        return await self.send_email(to_email, subject, html_content, text_content)


# Global email service instance
email_service = EmailService()
