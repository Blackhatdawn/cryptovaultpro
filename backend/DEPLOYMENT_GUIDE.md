# Backend Deployment Guide (Render)

## Production-safe deployment checklist

### 1) Configure Render environment variables/secrets
Set these in Render Dashboard (never commit actual secret values):

**Required secrets**
- `MONGO_URL`
- `JWT_SECRET`
- `CSRF_SECRET`
- `RESEND_API_KEY`
- `COINCAP_API_KEY`
- `NOWPAYMENTS_API_KEY`
- `NOWPAYMENTS_IPN_SECRET`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `SENTRY_DSN`

**Required non-secrets**
- `ENVIRONMENT=production`
- `DB_NAME=cryptovault`
- `PORT=8001`
- `APP_URL=https://www.cryptovault.financial`
- `PUBLIC_API_URL=https://cryptovault-api.onrender.com`
- `PUBLIC_WS_URL=wss://cryptovault-api.onrender.com`
- `PUBLIC_SOCKET_IO_PATH=/socket.io/`
- `UVICORN_LOOP=asyncio`
- `PYTHON_VERSION=3.11.11`

**CORS/hosted-frontend alignment**
- `CORS_ORIGINS` must include your exact frontend domain(s), for example:
  - `https://www.cryptovault.financial`
  - `https://cryptovault.financial`
  - `https://coinbase-love.vercel.app`

### 2) Deploy
- Trigger deployment from Render UI, or via CI pipeline in `.github/workflows/deploy.yml`.

### 3) Verify
```bash
curl -fsS https://cryptovault-api.onrender.com/health
curl -fsS https://cryptovault-api.onrender.com/ping
curl -fsS https://cryptovault-api.onrender.com/api/config
```

## URLs
- API: `https://cryptovault-api.onrender.com`
- Health: `https://cryptovault-api.onrender.com/health`
- API docs: `https://cryptovault-api.onrender.com/api/docs`
- Frontend: `https://www.cryptovault.financial`

## Security note
Never store production tokens, API keys, or DB credentials in repository files or scripts.
