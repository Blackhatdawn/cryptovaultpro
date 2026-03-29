#!/bin/bash
# ============================================
# COPY AND RUN THESE COMMANDS IN YOUR TERMINAL
# ============================================

# Step 1: Set all secrets (run once)
flyctl secrets set \
  MONGO_URL="mongodb+srv://<user>:<password>@<cluster>.mongodb.net/<db>?retryWrites=true&w=majority" \
  JWT_SECRET="<generate-a-strong-32+char-secret>" \
  CSRF_SECRET="<generate-a-strong-32+char-secret>" \
  EMAIL_SERVICE="resend" \
  RESEND_API_KEY="<your-resend-api-key>" \
  COINCAP_API_KEY="<your-coincap-api-key>" \
  NOWPAYMENTS_API_KEY="<your-nowpayments-api-key>" \
  NOWPAYMENTS_IPN_SECRET="<your-nowpayments-ipn-secret>" \
  UPSTASH_REDIS_REST_URL="https://<your-redis>.upstash.io" \
  UPSTASH_REDIS_REST_TOKEN="<your-upstash-token>" \
  SENTRY_DSN="<your-sentry-dsn>" \
  CORS_ORIGINS='["https://<your-frontend-domain>"]' \
  --app "<your-fly-app-name>"

# Step 2: Deploy
flyctl deploy --app "<your-fly-app-name>"

# Step 3: Verify deployment
flyctl status --app "<your-fly-app-name>"
curl "https://<your-app>.fly.dev/health"
