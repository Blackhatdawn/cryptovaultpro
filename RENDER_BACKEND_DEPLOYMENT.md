# 🚀 Render Backend Deployment - Production Guide

**Status**: ✅ Enterprise Ready | **Platform**: Render.com | **Framework**: FastAPI/Python

---

## 📋 Quick Start (5 Minutes)

### Prerequisites
- ✅ Render.com account created
- ✅ Backend repository pushed to GitHub
- ✅ Environment variables documented

### Deployment Steps

1. **Login to Render Dashboard** → https://dashboard.render.com

2. **Create New Web Service**
   - Click: "New +" → "Web Service"
   - Select: Your GitHub repository
   - Branch: `main`

3. **Configure Service**
   ```
   Name: cryptovault-api
   Environment: Python 3.11
   Region: Choose closest to users
   Plan: Standard (minimum for production)
   ```

4. **Build Command**
   ```bash
   pip install -r requirements.txt
   ```

5. **Start Command**
   ```bash
   gunicorn server:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --workers 4 --timeout 120
   ```

6. **Environment Variables** (Copy from table below)
   - Add all variables from "Production Variables" section
   - Use Render's secret manager for sensitive keys

7. **Deploy**
   - Click: "Create Web Service"
   - Wait for build and deployment
   - Check: https://your-service.onrender.com/health/ready

---

## 🔐 Environment Variables for Render

### Critical Secrets (Use Render Secrets Manager)

| Variable | Value | Source |
|----------|-------|--------|
| `MONGO_URL` | MongoDB Atlas connection string | MongoDB Atlas dashboard |
| `JWT_SECRET` | 32+ character random string | `openssl rand -hex 32` |
| `CSRF_SECRET` | 32+ character random string | `openssl rand -hex 32` |
| `REDIS_URL` | Upstash Redis connection string | Upstash dashboard |

### Required Variables

```
# Core App
APP_NAME=CryptoVault Pro
ENVIRONMENT=production
FULL_PRODUCTION_CONFIGURATION=true
DEBUG=false

# Server
HOST=0.0.0.0
PORT=8000  (Render sets this automatically)
WORKERS=4

# Frontend Integration
PUBLIC_API_URL=https://your-api.onrender.com
FRONTEND_DOMAIN=yourdomain.com
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Email Service (Choose one)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# External Services
COINCAP_API_KEY=your-coincap-key
TELEGRAM_BOT_TOKEN=your-telegram-token
SENTRY_DSN=your-sentry-dsn

# Optional but recommended
FIREBASE_PROJECT_ID=your-firebase-project
FIREBASE_PRIVATE_KEY=your-firebase-key
```

---

## 🌍 MongoDB Atlas Setup (Critical)

### Create Database
1. Login: https://account.mongodb.com/account/login
2. Create cluster in region near Render
3. Create database user: `cryptovault-prod`
4. Whitelist Render IP: Allow `0.0.0.0/0` (or Render's IP range)
5. Get connection string: `mongodb+srv://user:password@cluster.mongodb.net/dbname?retryWrites=true&w=majority`

### Test Connection
```bash
# From Render terminal
curl -X GET "https://your-service.onrender.com/health/ready"
# Should return: { "status": "ready", ... }
```

---

## 🔄 Redis Setup (Optional but Recommended)

### Use Upstash
1. Create account: https://upstash.com/
2. Create Redis database
3. Copy connection string: `redis://default:password@host:port`
4. Add to Render environment as `REDIS_URL`

### Without Redis
- Backend will use in-memory cache
- Not recommended for production with multiple instances
- Set `REDIS_URL` to empty string

---

## 📊 Render Configuration Details

### Web Service Settings
```
Name: cryptovault-api
Environment: Python 3.11
Region: Choose for latency (US, EU, etc.)
Plan: Standard or Standard Plus (1GB RAM minimum)
Disk: 50GB (auto-scaling SSD)
```

### Build Strategy
```
Use Buildpack (recommended) OR
Use Dockerfile (advanced)
```

### Auto-Deploy
```
✅ Deploy when you push to main branch
✅ Automatic deploys enabled
✅ Failed deploys don't replace working version
```

---

## ✅ Verification Checklist

### Post-Deployment
- [ ] Service is running (green status in Render dashboard)
- [ ] Health check passes: `GET /health/ready` → 200 status
- [ ] API docs accessible: `GET /.api/docs`
- [ ] Can authenticate: `POST /api/auth/login`
- [ ] Database connected: Check Render logs for "Connected to MongoDB"
- [ ] No errors in logs (Render dashboard → Logs)
- [ ] Response times < 100ms (check Render Metrics)

### Frontend Integration
- [ ] Frontend can reach API (check CORS_ORIGINS)
- [ ] WebSocket connects: `WS /socket.io/`
- [ ] Authentication tokens work
- [ ] Real-time updates work

### Security
- [ ] All secrets use Render's Secret Manager
- [ ] HTTPS enforced (automatic with Render)
- [ ] CORS_ORIGINS doesn't include `*`
- [ ] Rate limiting working (check logs)
- [ ] No debug logs in production (DEBUG=false)

---

## 🔧 Common Issues & Solutions

### Issue: Service Won't Start
**Error**: `gunicorn: error: '' is not a valid port number`
**Cause**: PORT environment variable not set properly
**Solution**: Render sets PORT automatically. Ensure start command uses `$PORT`

### Issue: Database Connection Failed
**Error**: `Connection refused to MongoDB`
**Causes**:
1. IP whitelist not configured in MongoDB Atlas
2. Database credentials wrong
3. Network timeout

**Solutions**:
```bash
# 1. Check MongoDB Atlas whitelist
# Allow 0.0.0.0/0 or Render's IP range

# 2. Verify connection string format
mongodb+srv://user:password@cluster.mongodb.net/db?retryWrites=true

# 3. Test from Render terminal
# Open Render Service → Shell → Run: python -c "from motor.motor_asyncio import AsyncIOMotorClient; print('OK')"
```

### Issue: CORS Errors in Frontend
**Error**: `Access to XMLHttpRequest blocked by CORS policy`
**Solution**:
```bash
# Update Render environment variable
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Redeploy service
```

### Issue: High Memory Usage
**Error**: Service restarting due to OOM
**Causes**:
1. Not enough allocated RAM
2. Memory leak in code
3. Too many concurrent connections

**Solutions**:
```bash
# 1. Upgrade Render plan (Standard Plus = 2GB)
# 2. Reduce workers: WORKERS=2 (instead of 4)
# 3. Check logs for memory issues
```

### Issue: Timeout Errors
**Error**: `504 Gateway Timeout`
**Causes**:
1. Slow database queries
2. External service timeouts
3. Worker threads too busy

**Solutions**:
```bash
# 1. Increase timeout in start command
gunicorn server:app ... --timeout 300

# 2. Add database indexes
# 3. Enable Redis caching (REDIS_URL)
```

---

## 📈 Performance Optimization

### Gunicorn Worker Configuration
```bash
# For production (4GB RAM)
WORKERS=4

# For standard tier (1GB RAM)  
WORKERS=2

# For development/staging
WORKERS=1

# Formula: CPU_CORES * 2 + 1 (typical)
```

### Database Optimization
```python
# Connection pooling is configured in config.py
# Min: 5, Max: 50 connections
# Adjust MONGO_POOL_MIN and MONGO_POOL_MAX if needed
```

### Caching Strategy
```bash
# With Redis (recommended)
REDIS_URL=redis://...
# Cache TTL: 1 hour for most data

# Without Redis (not recommended)
# Uses in-memory cache
# Limited to single instance
```

---

## 🔐 Security Hardening for Production

### Before Going Live
- [ ] Change all default secrets
  ```bash
  JWT_SECRET=$(openssl rand -hex 32)
  CSRF_SECRET=$(openssl rand -hex 32)
  ```

- [ ] Enable HTTPS (automatic on Render)

- [ ] Set tight CORS_ORIGINS
  ```
  CORS_ORIGINS=https://yourdomain.com
  (NOT: https://*, NOT: http://*)
  ```

- [ ] Use strong MongoDB password (16+ characters with symbols)

- [ ] Enable MongoDB network access control

- [ ] Store all secrets in Render Secret Manager (not in Git)

- [ ] Enable rate limiting
  ```
  RATE_LIMIT_ENABLED=true
  RATE_LIMIT_PER_MINUTE=60
  ```

### Monitoring
- [ ] Enable Sentry error tracking
  ```
  SENTRY_DSN=https://key@sentry.io/project
  ```

- [ ] Monitor logs regularly
- [ ] Set up alerts for errors
- [ ] Track response times

---

## 🚀 Deployment Workflow

### First Deployment
```
1. Create Render account
2. Configure MongoDB Atlas
3. Create Render Web Service
4. Add environment variables
5. Deploy (automatic from GitHub)
6. Run verification checklist
7. Point DNS to Render
```

### Updates & Redeployment
```
1. Push code changes to main branch
2. Render automatically redeploys
3. Check deployment status in dashboard
4. Verify health endpoint
5. Test frontend integration
```

### Rollback Procedure
```
1. Goto Render Dashboard
2. Click Service → Deployments
3. Find previous successful deployment
4. Click "Deploy"
5. Confirm rollback
6. Verify /health/ready endpoint
```

---

## 📞 Support Resources

### Render Documentation
- [Render Web Services Guide](https://render.com/docs/web-services)
- [Render Environment Variables](https://render.com/docs/environment-variables)
- [Render Troubleshooting](https://render.com/docs/troubleshooting)

### Backend Documentation
- [FastAPI Docs](./FRONTEND_BACKEND_INTEGRATION.md)
- [Environment Variables](./backend/.env.example)
- [Health Check Endpoints](./backend/server.py)

### External Services
- [MongoDB Atlas](https://www.mongodb.com/docs/atlas/)
- [Upstash Redis](https://upstash.com/docs)
- [Sentry Setup](https://docs.sentry.io/)

---

## 🎯 Success Criteria

✅ Service is live and running (green status)  
✅ Health check passes (200 status)  
✅ Database connected and responding  
✅ Frontend can communicate with API  
✅ WebSocket real-time updates working  
✅ Error rate < 0.5%  
✅ Response time < 100ms (p95)  
✅ No security warnings in logs  
✅ Monitoring/alerts configured  

---

## 🔗 Quick Links

| Action | Link |
|--------|------|
| Render Dashboard | https://dashboard.render.com |
| Service Logs | Render → Service → Logs |
| Environment Variables | Render → Service → Environment |
| Health Check | https://your-service.onrender.com/health/ready |
| API Documentation | https://your-service.onrender.com/.api/docs |

---

**Last Updated**: April 3, 2026  
**Status**: ✅ Production Ready  
**Framework**: FastAPI 0.110.1  
**Database**: MongoDB Atlas  
**Caching**: Upstash Redis (optional)  

---

**Next Step**: [Vercel Frontend Deployment Guide](./VERCEL_FRONTEND_DEPLOYMENT.md)
