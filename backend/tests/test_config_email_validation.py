import os
import sys

# Ensure importing backend.config's global settings stays in a safe baseline mode
os.environ["ENVIRONMENT"] = "development"
os.environ["EMAIL_SERVICE"] = "mock"
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Settings


def test_production_resend_requires_api_key():
    try:
        Settings(environment="production", email_service="resend", cors_origins=[])
        assert False, "Expected production resend config without RESEND_API_KEY to fail"
    except Exception as exc:
        assert "RESEND_API_KEY" in str(exc)


def test_production_resend_with_api_key_is_valid():
    settings = Settings(
        environment="production",
        email_service="resend",
        resend_api_key="re_test_key",
        cors_origins=[],
    )

    assert settings.email_service == "resend"


def test_production_smtp_requires_host():
    try:
        Settings(environment="production", email_service="smtp", cors_origins=[])
        assert False, "Expected production smtp config without SMTP_HOST to fail"
    except Exception as exc:
        assert "SMTP_HOST" in str(exc)
