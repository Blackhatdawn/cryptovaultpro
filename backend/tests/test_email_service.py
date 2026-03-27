import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_service import EmailService


@pytest.fixture
def svc():
    return EmailService()


def test_password_reset_template_uses_reset_confirm_route(svc: EmailService):
    subject, html_content, text_content = svc.get_password_reset_email(
        name="Alice",
        token="token123",
        app_url="https://example.com",
    )

    assert "Reset Your Password" in subject
    assert "https://example.com/reset?token=token123" in html_content
    assert "https://example.com/reset?token=token123" in text_content


def test_verification_template_contains_code_and_token(svc: EmailService):
    subject, html_content, text_content = svc.get_verification_email(
        name="Alice",
        code="123456",
        token="abc123",
        verification_url="https://example.com/verify",
    )

    assert "Verify" in subject
    assert "123456" in html_content
    assert "abc123" in html_content
    assert "123456" in text_content


@pytest.mark.asyncio
async def test_mock_send_returns_success(svc: EmailService):
    # call underlying mock sender directly so this remains deterministic
    result = await svc._send_mock("user@example.com", "Test Subject")
    assert result is True


@pytest.mark.asyncio
async def test_send_email_retries_for_resend_mode(svc: EmailService, monkeypatch):
    attempts = {"count": 0}

    async def fake_send_resend(to_email, subject, html_content, text_content):
        attempts["count"] += 1
        return attempts["count"] >= 2

    monkeypatch.setattr(svc, "mode", "resend")
    monkeypatch.setattr(svc, "_send_resend", fake_send_resend)

    result = await svc.send_email("user@example.com", "subject", "<p>html</p>", "text", retry=True)

    assert result is True
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_send_email_without_retry_calls_resend_once(svc: EmailService, monkeypatch):
    attempts = {"count": 0}

    async def fake_send_resend(to_email, subject, html_content, text_content):
        attempts["count"] += 1
        return False

    monkeypatch.setattr(svc, "mode", "resend")
    monkeypatch.setattr(svc, "_send_resend", fake_send_resend)

    result = await svc.send_email("user@example.com", "subject", "<p>html</p>", "text", retry=False)

    assert result is False
    assert attempts["count"] == 1
