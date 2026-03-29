#!/bin/bash
# ============================================
# FLY.IO SECRETS DEPLOYMENT SCRIPT
# CryptoVault Backend - Production
# ============================================
# 
# USAGE: ./set-fly-secrets.sh
#
# This script sets all SECRET environment variables
# Non-secrets are already in fly.toml [env] section
# ============================================

set -e

APP_NAME="coinbase-love"

echo "======================================"
echo "🔐 Setting Fly.io Secrets for $APP_NAME"
echo "======================================"

#
# IMPORTANT:
# - Do not hardcode secrets in this repo.
# - Export the required vars in your shell (or load from a secure secrets manager) before running.
#

: "${MONGO_URL:?Missing MONGO_URL}"
: "${JWT_SECRET:?Missing JWT_SECRET}"
: "${CSRF_SECRET:?Missing CSRF_SECRET}"

: "${EMAIL_SERVICE:?Missing EMAIL_SERVICE (sendgrid|resend|smtp)}"
if [ "$EMAIL_SERVICE" = "sendgrid" ]; then
  : "${SENDGRID_API_KEY:?Missing SENDGRID_API_KEY}"
elif [ "$EMAIL_SERVICE" = "resend" ]; then
  : "${RESEND_API_KEY:?Missing RESEND_API_KEY}"
elif [ "$EMAIL_SERVICE" = "smtp" ]; then
  : "${SMTP_HOST:?Missing SMTP_HOST}"
fi

: "${COINCAP_API_KEY:?Missing COINCAP_API_KEY}"
: "${NOWPAYMENTS_API_KEY:?Missing NOWPAYMENTS_API_KEY}"
: "${NOWPAYMENTS_IPN_SECRET:?Missing NOWPAYMENTS_IPN_SECRET}"
: "${UPSTASH_REDIS_REST_URL:?Missing UPSTASH_REDIS_REST_URL}"
: "${UPSTASH_REDIS_REST_TOKEN:?Missing UPSTASH_REDIS_REST_TOKEN}"

# Optional
FIREBASE_CREDENTIALS_BASE64="${FIREBASE_CREDENTIALS_BASE64:-}"
SENTRY_DSN="${SENTRY_DSN:-}"
CORS_ORIGINS="${CORS_ORIGINS:-[]}"

flyctl secrets set \
  MONGO_URL="$MONGO_URL" \
  JWT_SECRET="$JWT_SECRET" \
  CSRF_SECRET="$CSRF_SECRET" \
  EMAIL_SERVICE="$EMAIL_SERVICE" \
  SENDGRID_API_KEY="${SENDGRID_API_KEY:-}" \
  RESEND_API_KEY="${RESEND_API_KEY:-}" \
  SMTP_HOST="${SMTP_HOST:-}" \
  SMTP_PORT="${SMTP_PORT:-}" \
  SMTP_USERNAME="${SMTP_USERNAME:-}" \
  SMTP_PASSWORD="${SMTP_PASSWORD:-}" \
  COINCAP_API_KEY="$COINCAP_API_KEY" \
  NOWPAYMENTS_API_KEY="$NOWPAYMENTS_API_KEY" \
  NOWPAYMENTS_IPN_SECRET="$NOWPAYMENTS_IPN_SECRET" \
  UPSTASH_REDIS_REST_URL="$UPSTASH_REDIS_REST_URL" \
  UPSTASH_REDIS_REST_TOKEN="$UPSTASH_REDIS_REST_TOKEN" \
  SENTRY_DSN="$SENTRY_DSN" \
  CORS_ORIGINS="$CORS_ORIGINS" \
  FIREBASE_CREDENTIALS_BASE64="$FIREBASE_CREDENTIALS_BASE64" \
  --app "$APP_NAME"

echo ""
echo "✅ All secrets set successfully!"
echo ""
echo "📋 Verify with: flyctl secrets list --app $APP_NAME"
echo ""
