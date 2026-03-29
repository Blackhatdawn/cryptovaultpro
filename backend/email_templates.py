"""
Transactional email templates for CryptoVault.

Goals:
- Consistent branding (pulled from settings)
- Lightweight HTML (avoid heavy footers/social blocks)
- Good rendering on iOS Mail and common clients (table layout, inline styles, responsive padding)
- Deliverability-friendly copy (no emoji-heavy subjects required, limited links/images)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape as _escape
from typing import Optional

from config import settings


def _brand_name() -> str:
    # Prefer the "From" display name, then public branding.
    name = (getattr(settings, "email_from_name", "") or "").strip()
    if name:
        return name
    name = (getattr(settings, "public_site_name", "") or "").strip()
    if name:
        return name
    return (getattr(settings, "app_name", "") or "CryptoVault").strip()


def _site_url() -> str:
    url = (getattr(settings, "app_url", "") or "").strip()
    if not url:
        return "https://www.cryptovaultpro.finance"
    return url.rstrip("/")


BRAND_NAME = _brand_name()
SITE_URL = _site_url()
LOGO_URL = (getattr(settings, "public_logo_url", None) or f"{SITE_URL}/logo.svg").strip()
SUPPORT_EMAIL = (
    (getattr(settings, "public_support_email", None) or getattr(settings, "email_from", None) or "").strip()
    or "support@cryptovaultpro.finance"
)

# Minimal brand palette (dark, but simple).
_BG = "#0b0b0c"
_CARD = "#141416"
_BORDER = "#2a2a2d"
_TEXT = "#ffffff"
_MUTED = "#a1a1aa"
_PRIMARY = "#C5A049"
_DANGER = "#ef4444"


@dataclass(frozen=True)
class EmailParts:
    subject: str
    html: str
    text: str


def _e(value: object) -> str:
    """HTML-escape dynamic content to prevent injection and broken markup."""
    if value is None:
        return ""
    return _escape(str(value), quote=True)


def _format_url(url: str) -> str:
    return (url or "").strip()


def _button(url: str, label: str) -> str:
    href = _e(_format_url(url))
    text = _e(label)
    if not href:
        return ""
    return (
        f'<a href="{href}" '
        f'style="display:inline-block;background:{_PRIMARY};color:{_BG};'
        f'font-weight:700;font-size:15px;line-height:1;'
        f'padding:14px 22px;border-radius:10px;text-decoration:none;">'
        f"{text}</a>"
    )


def _mono_box(value: str) -> str:
    return (
        f'<div style="margin:16px 0;padding:14px 16px;background:#0f0f11;'
        f'border:1px solid {_BORDER};border-radius:12px;'
        f'font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \'Liberation Mono\', \'Courier New\', monospace;'
        f'font-size:22px;font-weight:800;letter-spacing:3px;color:{_TEXT};text-align:center;">'
        f"{_e(value)}</div>"
    )


def _kv_table(rows: list[tuple[str, str]]) -> str:
    rendered = []
    for k, v in rows:
        rendered.append(
            "<tr>"
            f'<td style="padding:10px 0;color:{_MUTED};font-size:12px;width:38%;">{_e(k)}</td>'
            f'<td style="padding:10px 0;color:{_TEXT};font-size:13px;">{_e(v)}</td>'
            "</tr>"
        )
    return (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" '
        f'style="margin:16px 0;border-top:1px solid {_BORDER};">'
        + "".join(rendered)
        + "</table>"
    )


def get_base_template(content: str, preheader: str = "") -> str:
    """
    Base email shell.
    Content should already be safe HTML (dynamic values escaped before interpolation).
    """
    pre = _e(preheader)
    year = datetime.now(timezone.utc).year
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{_e(BRAND_NAME)}</title>
  <style>
    @media (max-width: 600px) {{
      .container {{ width: 100% !important; }}
      .px {{ padding-left: 16px !important; padding-right: 16px !important; }}
      .pt {{ padding-top: 18px !important; }}
      .pb {{ padding-bottom: 18px !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background:{_BG};-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:{_BG};opacity:0;">
    {pre}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  </div>
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:{_BG};">
    <tr>
      <td align="center" style="padding:28px 14px;">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" class="container" style="width:100%;max-width:600px;background:{_CARD};border:1px solid {_BORDER};border-radius:16px;overflow:hidden;">
          <tr>
            <td align="center" class="px pt" style="padding:26px 26px 16px;">
              <a href="{_e(SITE_URL)}" style="text-decoration:none;">
                <img src="{_e(LOGO_URL)}" width="48" height="48" alt="{_e(BRAND_NAME)}" style="display:block;border:0;outline:none;text-decoration:none;">
              </a>
              <div style="margin-top:12px;font-size:18px;font-weight:800;color:{_TEXT};letter-spacing:0.2px;">
                {_e(BRAND_NAME)}
              </div>
            </td>
          </tr>
          <tr>
            <td class="px pb" style="padding:10px 26px 22px;">
              {content}
            </td>
          </tr>
          <tr>
            <td class="px" style="padding:16px 26px 24px;border-top:1px solid {_BORDER};">
              <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.5;text-align:center;">
                Need help? Contact <a href="mailto:{_e(SUPPORT_EMAIL)}" style="color:{_PRIMARY};text-decoration:none;">{_e(SUPPORT_EMAIL)}</a>
              </p>
              <p style="margin:10px 0 0;color:{_MUTED};font-size:11px;line-height:1.5;text-align:center;">
                © {year} {_e(BRAND_NAME)}. This is an automated message, please do not reply.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ----------------------------
# Auth / Account Emails
# ----------------------------

def email_verification(name: str, otp_code: str, verify_link: Optional[str] = None) -> str:
    """Email verification with OTP code and optional verify link."""
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Verify your email</h2>
      <p style="margin:0 0 14px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, use this code to verify your email address.
      </p>
      {_mono_box(otp_code)}
      <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">
        This code expires in 24 hours. If you did not create an account, you can ignore this email.
      </p>
    """
    if verify_link:
        content += f"""
          <div style="margin:18px 0 6px;text-align:center;">
            {_button(verify_link, "Verify email")}
          </div>
          <p style="margin:10px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;word-break:break-word;">
            Or open this link: <a href="{_e(verify_link)}" style="color:{_PRIMARY};text-decoration:none;">{_e(verify_link)}</a>
          </p>
        """
    content += f"""
      <div style="margin-top:16px;padding:12px 14px;background:#0f0f11;border:1px solid {_BORDER};border-radius:12px;">
        <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">
          Security tip: {_e(BRAND_NAME)} will never ask you for your password, recovery phrase, or 2FA codes by email.
        </p>
      </div>
    """
    return get_base_template(content, f"Your verification code is {otp_code}.")


def email_verification_text(name: str, otp_code: str, verify_link: Optional[str] = None) -> str:
    lines = [
        f"{BRAND_NAME} - Verify your email",
        "",
        f"Hi {name},",
        "",
        f"Your verification code is: {otp_code}",
        "This code expires in 24 hours.",
    ]
    if verify_link:
        lines += ["", f"Verify link: {verify_link}"]
    lines += [
        "",
        "If you did not create an account, you can ignore this email.",
        "",
        f"Support: {SUPPORT_EMAIL}",
    ]
    return "\n".join(lines)


def welcome_email(name: str) -> str:
    """Welcome email (post verification)."""
    dashboard_url = f"{SITE_URL}/dashboard"
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Welcome</h2>
      <p style="margin:0 0 14px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, your account is verified and ready to use.
      </p>
      <div style="margin:18px 0 6px;text-align:center;">
        {_button(dashboard_url, "Open dashboard")}
      </div>
      <p style="margin:10px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;word-break:break-word;">
        Dashboard link: <a href="{_e(dashboard_url)}" style="color:{_PRIMARY};text-decoration:none;">{_e(dashboard_url)}</a>
      </p>
    """
    return get_base_template(content, "Your account is ready.")


def welcome_email_text(name: str) -> str:
    dashboard_url = f"{SITE_URL}/dashboard"
    return "\n".join(
        [
            f"{BRAND_NAME} - Welcome",
            "",
            f"Hi {name},",
            "",
            "Your account is verified and ready to use.",
            "",
            f"Open dashboard: {dashboard_url}",
            "",
            f"Support: {SUPPORT_EMAIL}",
        ]
    )


def password_reset(name: str, reset_link: str) -> str:
    """Password reset email."""
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Reset your password</h2>
      <p style="margin:0 0 14px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, we received a request to reset your password. This link expires in 1 hour.
      </p>
      <div style="margin:18px 0 6px;text-align:center;">
        {_button(reset_link, "Reset password")}
      </div>
      <p style="margin:10px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;word-break:break-word;">
        Or open this link: <a href="{_e(reset_link)}" style="color:{_PRIMARY};text-decoration:none;">{_e(reset_link)}</a>
      </p>
      <p style="margin:14px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;">
        If you did not request this, you can ignore this email.
      </p>
    """
    return get_base_template(content, "Reset your password.")


def password_reset_text(name: str, reset_link: str) -> str:
    return "\n".join(
        [
            f"{BRAND_NAME} - Reset your password",
            "",
            f"Hi {name},",
            "",
            "Reset link (expires in 1 hour):",
            reset_link,
            "",
            "If you did not request this, you can ignore this email.",
            "",
            f"Support: {SUPPORT_EMAIL}",
        ]
    )


# ----------------------------
# Funds / Activity Emails
# ----------------------------

def deposit_confirmation(name: str, amount: str, asset: str, tx_hash: str) -> str:
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Deposit received</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, your deposit has been recorded.
      </p>
      {_kv_table([('Amount', f'{amount} {asset}'), ('Transaction', tx_hash)])}
      <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">
        If you do not recognize this activity, contact support immediately.
      </p>
    """
    return get_base_template(content, "Deposit received.")


def withdrawal_confirmation(name: str, amount: str, asset: str, address: str, tx_hash: str) -> str:
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Withdrawal initiated</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, your withdrawal request has been initiated.
      </p>
      {_kv_table([('Amount', f'{amount} {asset}'), ('To address', address), ('Transaction', tx_hash)])}
      <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">
        If you did not request this withdrawal, secure your account and contact support.
      </p>
    """
    return get_base_template(content, "Withdrawal initiated.")


def two_factor_reminder(name: str) -> str:
    url = f"{SITE_URL}/dashboard?setup=2fa"
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Enable two-factor authentication</h2>
      <p style="margin:0 0 12px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, enabling 2FA significantly improves your account security.
      </p>
      <div style="margin:18px 0 6px;text-align:center;">
        {_button(url, "Enable 2FA")}
      </div>
      <p style="margin:10px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;">
        You can enable 2FA from your account security settings.
      </p>
    """
    return get_base_template(content, "Enable 2FA to protect your account.")


def security_alert(name: str, alert_type: str, details: str, ip_address: str, location: str) -> str:
    secure_url = f"{SITE_URL}/dashboard?security=true"
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Security alert</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, we detected {_e(alert_type)} on your account.
      </p>
      {_kv_table([('Details', details), ('IP address', ip_address), ('Location', location)])}
      <div style="margin:18px 0 6px;text-align:center;">
        {_button(secure_url, "Review security")}
      </div>
      <p style="margin:10px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;">
        If this wasn’t you, change your password and enable 2FA immediately.
      </p>
    """
    return get_base_template(content, "Security alert.")


def security_alert_text(name: str, alert_type: str, details: str, ip_address: str, location: str) -> str:
    return "\n".join(
        [
            f"{BRAND_NAME} - Security alert",
            "",
            f"Hi {name},",
            "",
            f"Alert type: {alert_type}",
            f"Details: {details}",
            f"IP address: {ip_address}",
            f"Location: {location}",
            "",
            f"Review security: {SITE_URL}/dashboard?security=true",
            "",
            f"Support: {SUPPORT_EMAIL}",
        ]
    )


def kyc_status_update(name: str, status: str, tier: int, message: str) -> str:
    status_norm = (status or "").strip().lower()
    badge_color = _PRIMARY if status_norm == "approved" else _DANGER if status_norm == "rejected" else _MUTED
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">KYC status update</h2>
      <p style="margin:0 0 12px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, your identity verification status has been updated.
      </p>
      <div style="margin:12px 0;padding:12px 14px;border:1px solid {_BORDER};border-radius:12px;background:#0f0f11;">
        <div style="font-size:12px;color:{_MUTED};">Status</div>
        <div style="margin-top:4px;font-size:14px;font-weight:800;color:{badge_color};text-transform:capitalize;">{_e(status_norm or 'updated')}</div>
        <div style="margin-top:8px;font-size:12px;color:{_MUTED};">Tier</div>
        <div style="margin-top:4px;font-size:13px;color:{_TEXT};">{_e(tier)}</div>
      </div>
      <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">
        {_e(message)}
      </p>
    """
    return get_base_template(content, "KYC status updated.")


def kyc_status_update_text(name: str, status: str, tier: int, message: str) -> str:
    status_norm = (status or "").strip().lower() or "updated"
    return "\n".join(
        [
            f"{BRAND_NAME} - KYC status update",
            "",
            f"Hi {name},",
            "",
            f"Status: {status_norm}",
            f"Tier: {tier}",
            "",
            message,
            "",
            f"Support: {SUPPORT_EMAIL}",
        ]
    )


def p2p_transfer_sent(
    sender_name: str,
    recipient_name: str,
    recipient_email: str,
    amount: str,
    asset: str,
    gas_fee: str,
    transaction_id: str,
    note: Optional[str] = None,
) -> str:
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Transfer sent</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(sender_name)}, you sent funds to {_e(recipient_name)}.
      </p>
      {_kv_table([
        ('Recipient', f'{recipient_name} <{recipient_email}>'),
        ('Amount', f'{amount} {asset}'),
        ('Estimated fee', gas_fee),
        ('Transaction ID', transaction_id),
      ])}
    """
    if note:
        content += f"""
          <div style="margin:12px 0;padding:12px 14px;border:1px solid {_BORDER};border-radius:12px;background:#0f0f11;">
            <div style="font-size:12px;color:{_MUTED};margin-bottom:6px;">Note</div>
            <div style="font-size:13px;color:{_TEXT};line-height:1.55;">{_e(note)}</div>
          </div>
        """
    return get_base_template(content, "Transfer sent.")


def p2p_transfer_sent_text(
    sender_name: str,
    recipient_name: str,
    recipient_email: str,
    amount: str,
    asset: str,
    gas_fee: str,
    transaction_id: str,
    note: Optional[str] = None,
) -> str:
    lines = [
        f"{BRAND_NAME} - Transfer sent",
        "",
        f"Hi {sender_name},",
        "",
        f"Recipient: {recipient_name} <{recipient_email}>",
        f"Amount: {amount} {asset}",
        f"Estimated fee: {gas_fee}",
        f"Transaction ID: {transaction_id}",
    ]
    if note:
        lines += ["", f"Note: {note}"]
    lines += ["", f"Support: {SUPPORT_EMAIL}"]
    return "\n".join(lines)


def p2p_transfer_received(
    recipient_name: str,
    sender_name: str,
    sender_email: str,
    amount: str,
    asset: str,
    transaction_id: str,
    note: Optional[str] = None,
) -> str:
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Funds received</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(recipient_name)}, you received funds from {_e(sender_name)}.
      </p>
      {_kv_table([
        ('Sender', f'{sender_name} <{sender_email}>'),
        ('Amount', f'{amount} {asset}'),
        ('Transaction ID', transaction_id),
      ])}
    """
    if note:
        content += f"""
          <div style="margin:12px 0;padding:12px 14px;border:1px solid {_BORDER};border-radius:12px;background:#0f0f11;">
            <div style="font-size:12px;color:{_MUTED};margin-bottom:6px;">Note</div>
            <div style="font-size:13px;color:{_TEXT};line-height:1.55;">{_e(note)}</div>
          </div>
        """
    return get_base_template(content, "Funds received.")


def p2p_transfer_received_text(
    recipient_name: str,
    sender_name: str,
    sender_email: str,
    amount: str,
    asset: str,
    transaction_id: str,
    note: Optional[str] = None,
) -> str:
    lines = [
        f"{BRAND_NAME} - Funds received",
        "",
        f"Hi {recipient_name},",
        "",
        f"Sender: {sender_name} <{sender_email}>",
        f"Amount: {amount} {asset}",
        f"Transaction ID: {transaction_id}",
    ]
    if note:
        lines += ["", f"Note: {note}"]
    lines += ["", f"Support: {SUPPORT_EMAIL}"]
    return "\n".join(lines)


def price_alert_triggered(
    name: str,
    asset: str,
    current_price: str,
    target_price: str,
    condition: str,
    alert_id: str,
) -> str:
    condition_norm = (condition or "").strip().lower()
    condition_text = "above" if condition_norm == "above" else "below"
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Price alert</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, your alert for {_e(asset)} was triggered.
      </p>
      {_kv_table([
        ('Asset', asset),
        ('Condition', f'{condition_text} {target_price}'),
        ('Current price', current_price),
        ('Alert ID', alert_id),
      ])}
      <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">
        You can manage alerts in your dashboard.
      </p>
    """
    return get_base_template(content, "Price alert triggered.")


def price_alert_triggered_text(
    name: str,
    asset: str,
    current_price: str,
    target_price: str,
    condition: str,
    alert_id: str,
) -> str:
    condition_norm = (condition or "").strip().lower()
    condition_text = "above" if condition_norm == "above" else "below"
    return "\n".join(
        [
            f"{BRAND_NAME} - Price alert",
            "",
            f"Hi {name},",
            "",
            f"Asset: {asset}",
            f"Condition: {condition_text} {target_price}",
            f"Current price: {current_price}",
            f"Alert ID: {alert_id}",
            "",
            f"Manage alerts: {SITE_URL}/dashboard",
            "",
            f"Support: {SUPPORT_EMAIL}",
        ]
    )


def admin_otp_email(admin_name: str, otp_code: str, ip_address: str) -> str:
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">Admin sign-in verification</h2>
      <p style="margin:0 0 14px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(admin_name)}, use this code to complete your admin login. This code expires in 5 minutes.
      </p>
      {_mono_box(otp_code)}
      <p style="margin:10px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;">
        Request IP: <span style="font-family:ui-monospace,Menlo,Monaco,Consolas,monospace;">{_e(ip_address)}</span>
      </p>
      <div style="margin-top:14px;padding:12px 14px;border:1px solid rgba(239,68,68,0.35);border-radius:12px;background:rgba(239,68,68,0.08);">
        <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">
          If you did not attempt to sign in, contact your security team immediately.
        </p>
      </div>
    """
    return get_base_template(content, f"Admin OTP: {otp_code}")


def admin_otp_email_text(admin_name: str, otp_code: str, ip_address: str) -> str:
    return "\n".join(
        [
            f"{BRAND_NAME} - Admin sign-in verification",
            "",
            f"Hi {admin_name},",
            "",
            f"OTP code (expires in 5 minutes): {otp_code}",
            f"Request IP: {ip_address}",
            "",
            f"Support: {SUPPORT_EMAIL}",
        ]
    )


def login_new_device(
    name: str,
    device: str,
    browser: str,
    ip_address: str,
    location: str,
    login_time: str,
) -> str:
    secure_url = f"{SITE_URL}/dashboard?security=true"
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">New login detected</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        Hi {_e(name)}, we detected a login from a new device.
      </p>
      {_kv_table([
        ('Device', device),
        ('Browser', browser),
        ('IP address', ip_address),
        ('Location', location),
        ('Time', login_time),
      ])}
      <div style="margin:18px 0 6px;text-align:center;">
        {_button(secure_url, "Secure account")}
      </div>
      <p style="margin:10px 0 0;color:{_MUTED};font-size:12px;line-height:1.6;">
        If this wasn’t you, reset your password and enable 2FA.
      </p>
    """
    return get_base_template(content, "New login detected.")


def login_new_device_text(
    name: str,
    device: str,
    browser: str,
    ip_address: str,
    location: str,
    login_time: str,
) -> str:
    return "\n".join(
        [
            f"{BRAND_NAME} - New login detected",
            "",
            f"Hi {name},",
            "",
            f"Device: {device}",
            f"Browser: {browser}",
            f"IP address: {ip_address}",
            f"Location: {location}",
            f"Time: {login_time}",
            "",
            f"Secure account: {SITE_URL}/dashboard?security=true",
            "",
            f"Support: {SUPPORT_EMAIL}",
        ]
    )


# ----------------------------
# Support / Internal Emails
# ----------------------------

def contact_submission_internal(
    name: str,
    email: str,
    company: Optional[str],
    phone: Optional[str],
    subject: str,
    message: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> EmailParts:
    pre = f"New contact request: {subject}"
    content = f"""
      <h2 style="margin:0 0 10px;color:{_TEXT};font-size:20px;line-height:1.25;">New contact submission</h2>
      <p style="margin:0 0 10px;color:{_MUTED};font-size:14px;line-height:1.6;">
        A user submitted the contact form on {_e(BRAND_NAME)}.
      </p>
      {_kv_table([
        ('Name', name),
        ('Email', email),
        ('Company', company or '-'),
        ('Phone', phone or '-'),
        ('Subject', subject),
        ('IP', ip_address or '-'),
      ])}
      <div style="margin-top:12px;padding:12px 14px;border:1px solid {_BORDER};border-radius:12px;background:#0f0f11;">
        <div style="font-size:12px;color:{_MUTED};margin-bottom:8px;">Message</div>
        <div style="font-size:13px;color:{_TEXT};line-height:1.6;white-space:pre-wrap;">{_e(message)}</div>
      </div>
      <p style="margin:12px 0 0;color:{_MUTED};font-size:11px;line-height:1.6;">
        User-Agent: {_e(user_agent or '-')}
      </p>
    """
    html = get_base_template(content, pre)
    text = "\n".join(
        [
            f"{BRAND_NAME} - Contact submission",
            "",
            f"Name: {name}",
            f"Email: {email}",
            f"Company: {company or '-'}",
            f"Phone: {phone or '-'}",
            f"Subject: {subject}",
            f"IP: {ip_address or '-'}",
            "",
            "Message:",
            message,
            "",
            f"User-Agent: {user_agent or '-'}",
        ]
    )
    return EmailParts(subject=f"[Contact] {subject}", html=html, text=text)
