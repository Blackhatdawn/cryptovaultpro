# 🚀 Production Deployment Checklist - Vercel + Render

**Status**: ✅ Ready for Live Business | **Duration**: 1-2 hours  
**Last Updated**: April 3, 2026

---

## 🎯 Phase Overview

```
Phase 1: Preparation (15 min)
Phase 2: Backend on Render (30 min)
Phase 3: Frontend on Vercel (20 min)
Phase 4: Integration Testing (20 min)
Phase 5: Security Verification (15 min)
Phase 6: Live Launch (10 min)
Phase 7: Post-Launch Monitoring (30 min+)
```

---

# PHASE 1: PREPARATION (15 MINUTES)

## 1.1 Accounts & Access
- [ ] Render.com account created
- [ ] Vercel.com account created
- [ ] GitHub account with both repos accessed
- [ ] MongoDB Atlas account created
- [ ] Domain name registered (if using custom domain)
- [ ] DNS control (for domain setup)

## 1.2 Pre-Deployment Checks
- [ ] Backend code committed and pushed to GitHub
- [ ] Frontend code committed and pushed to GitHub
- [ ] `.env` and secrets NOT committed to Git
- [ ] `render.yaml` exists in root directory
- [ ] `vercel.json` exists in root directory
- [ ] All dependencies pinned with exact versions

## 1.3 Documentation Ready
- [ ] Read [RENDER_BACKEND_DEPLOYMENT.md](./RENDER_BACKEND_DEPLOYMENT.md)
- [ ] Read [VERCEL_FRONTEND_DEPLOYMENT.md](./VERCEL_FRONTEND_DEPLOYMENT.md)
- [ ] Have list of environment variables prepared
- [ ] Have MongoDB Atlas credentials ready
- [ ] Have external API keys ready (if any)

---

# PHASE 2: BACKEND ON RENDER (30 MINUTES)

## 2.1 MongoDB Atlas Setup

- [ ] **Create Database**
  - [ ] Login to MongoDB Atlas: https://account.mongodb.com
  - [ ] Create or select existing cluster
  - [ ] Choose region closer to users
  - [ ] Create database user: `cryptovault-prod`
  - [ ] Set strong password (16+ characters, symbols)
  - [ ] Get connection string

- [ ] **Network Access**
  - [ ] Whitelist IP: `0.0.0.0/0` (Render can have dynamic IPs)
  - Alternatively: Add Render's static IP if available
  - [ ] Test connection: `mongosh "<connection-string>"`

## 2.2 Create Render Web Service

- [ ] **Connect Repository**
  - [ ] Login to Render: https://dashboard.render.com
  - [ ] Click: "New +" → "Web Service"
  - [ ] Select GitHub repository
  - [ ] Branch: `main`
  - [ ] Authorization granted to repository

- [ ] **Service Configuration**
  - [ ] **Name**: `cryptovault-api`
  - [ ] **Environment**: Python 3.11
  - [ ] **Region**: Choose closest to users
  - [ ] **Plan**: Standard ($7/month minimum)
  - [ ] **Build Command**: `pip install -r requirements.txt`
  - [ ] **Start Command**: 
    ```bash
    gunicorn server:app -k uvicorn.workers.UvicornWorker \
      --bind 0.0.0.0:$PORT --workers 4 --timeout 120
    ```

## 2.3 Environment Variables (Render Secrets Manager)

- [ ] **Critical Secrets** (Use Secret values, not text)
  - [ ] `MONGO_URL`: `mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true`
  - [ ] `JWT_SECRET`: `$(openssl rand -hex 32)`
  - [ ] `CSRF_SECRET`: `$(openssl rand -hex 32)`
  - [ ] `REDIS_URL`: (if using Upstash Redis)

- [ ] **Application Configuration**
  - [ ] `APP_NAME`: CryptoVault Pro
  - [ ] `ENVIRONMENT`: production
  - [ ] `FULL_PRODUCTION_CONFIGURATION`: true
  - [ ] `DEBUG`: false
  - [ ] `HOST`: 0.0.0.0
  - [ ] `WORKERS`: 4

- [ ] **Frontend Integration**
  - [ ] `PUBLIC_API_URL`: https://cryptovault-api.onrender.com
  - [ ] `FRONTEND_DOMAIN`: yourdomain.com
  - [ ] `CORS_ORIGINS`: https://yourdomain.com,https://www.yourdomain.com

- [ ] **Email Service** (Choose one)
  - [ ] `SMTP_SERVER`: smtp.gmail.com
  - [ ] `SMTP_PORT`: 587
  - [ ] `SMTP_USERNAME`: your-email@gmail.com
  - [ ] `SMTP_PASSWORD`: app-specific password

- [ ] **External Services** (as applicable)
  - [ ] `TELEGRAM_BOT_TOKEN`: (if using Telegram)
  - [ ] `SENTRY_DSN`: (optional, for error tracking)

## 2.4 Deploy Backend

- [ ] **Initiate Deployment**
  - [ ] Click: "Create Web Service"
  - [ ] Wait for build completion (2-5 minutes)
  - [ ] Watch logs for errors
  - [ ] Service should show "Live" status (green)

- [ ] **Verify Deployment**
  - [ ] Check build logs: "Build successful"
  - [ ] Service status: 🟢 LIVE
  - [ ] No errors in logs
  - [ ] Health endpoint accessible

- [ ] **Test Health Endpoint**
  ```bash
  curl https://cryptovault-api.onrender.com/health/ready
  # Expected: { "status": "ready", "timestamp": "...", ... }
  ```

- [ ] **Save Render URL**
  - [ ] Backend URL: `https://cryptovault-api.onrender.com`
  - [ ] Use this for Vercel REACT_APP_API_URL

---

# PHASE 3: FRONTEND ON VERCEL (20 MINUTES)

## 3.1 Import to Vercel

- [ ] **Connect Repository**
  - [ ] Login to Vercel: https://vercel.com/dashboard
  - [ ] Click: "Add New..." → "Project"
  - [ ] Select GitHub
  - [ ] Choose frontend repository
  - [ ] Authorize access if prompted

- [ ] **Project Settings**
  - [ ] **Project Name**: cryptovault-frontend
  - [ ] **Framework**: React (auto-detected)
  - [ ] **Build Command**: npm run build
  - [ ] **Output Directory**: build
  - [ ] **Install Command**: npm install
  - [ ] **Node Version**: 18.x (LTS)

## 3.2 Environment Variables

- [ ] **Add to Vercel** (Settings → Environment Variables)
  - [ ] `REACT_APP_API_URL`: https://cryptovault-api.onrender.com
  - [ ] `REACT_APP_WEBSOCKET_URL`: wss://cryptovault-api.onrender.com
  - [ ] `REACT_APP_API_TIMEOUT`: 30000
  - [ ] `REACT_APP_ENABLE_ANALYTICS`: true
  - [ ] `REACT_APP_ENVIRONMENT`: production

## 3.3 Deploy Frontend

- [ ] **Initiate Deployment**
  - [ ] Click: "Deploy"
  - [ ] Watch build progress
  - [ ] Build should complete in 1-3 minutes
  - [ ] Status should show "Ready"

- [ ] **Verify Deployment**
  - [ ] Frontend URL: `https://cryptovault-frontend.vercel.app`
  - [ ] Site loads without errors
  - [ ] No build errors in logs
  - [ ] Pages are interactive

---

# PHASE 4: INTEGRATION TESTING (20 MINUTES)

## 4.1 Frontend-Backend Communication

- [ ] **Test API Connectivity**
  - [ ] Open browser console (F12)
  - [ ] Go to https://cryptovault-frontend.vercel.app
  - [ ] Check Network tab - no CORS errors
  - [ ] Test login: POST to `/api/auth/login`
  - [ ] Response received correctly

- [ ] **Test WebSocket**
  - [ ] Open browser console
  - [ ] Check for WebSocket connection to `/socket.io/`
  - [ ] Should show: `WebSocket [wss://...] Connected`
  - [ ] No connection errors

## 4.2 Authentication Flow

- [ ] **Login/Register Flow**
  - [ ] Create test account on frontend
  - [ ] Submit registration form
  - [ ] Account created in MongoDB
  - [ ] Can log in with new account
  - [ ] JWT token received and stored

- [ ] **Token Validation**
  - [ ] Check: Cookie/localStorage has JWT
  - [ ] Token valid format: 3 dot-separated sections
  - [ ] Subsequent requests include token in header

## 4.3 Real-Time Features

- [ ] **WebSocket Updates** (if applicable)
  - [ ] Open site in two windows
  - [ ] Perform action in one window
  - [ ] Other window receives real-time update
  - [ ] No WebSocket errors in console

## 4.4 Error Handling

- [ ] **API Errors Display**
  - [ ] Try invalid login
  - [ ] Frontend displays error message properly
  - [ ] No stack traces or sensitive info shown
  - [ ] User experience is smooth

- [ ] **Network Errors**
  - [ ] Test offline: DevTools → Network → Offline
  - [ ] Frontend shows loading state
  - [ ] Error message displays on failure
  - [ ] Can recover when online

---

# PHASE 5: SECURITY VERIFICATION (15 MINUTES)

## 5.1 Frontend Security

- [ ] **CORS Verification**
  - [ ] Open browser console
  - [ ] No CORS errors
  - [ ] API responses successful
  - [ ] Only allowed domains can access API

- [ ] **Secrets Check**
  - [ ] No API keys in source code
  - [ ] No hardcoded secrets visible
  - [ ] All secrets in Vercel environment
  - [ ] .env file never committed to Git

- [ ] **HTTPS Enforcement**
  - [ ] Site loads over HTTPS only
  - [ ] Mixed content warnings: none
  - [ ] Redirect HTTP → HTTPS: active

- [ ] **Security Headers**
  - [ ] Open DevTools → Network → Response Headers
  - [ ] Check for security headers
  - [ ] Content-Security-Policy present
  - [ ] X-Frame-Options: DENY or SAMEORIGIN

## 5.2 Backend Security

- [ ] **Secrets Management**
  - [ ] All secrets in Render Secret Manager
  - [ ] `.env` file not in Git
  - [ ] JWT_SECRET is 32+ characters
  - [ ] CSRF_SECRET is 32+ characters

- [ ] **CORS Configuration**
  - [ ] CORS_ORIGINS set to specific domains
  - [ ] No wildcard (*) in CORS_ORIGINS
  - [ ] Frontend domain included
  - [ ] API rejects unauthorized origins

- [ ] **Database Security**
  - [ ] MongoDB password strong (16+ chars)
  - [ ] Database user has limited permissions
  - [ ] IP whitelist configured
  - [ ] Connection uses SSL/TLS

- [ ] **Rate Limiting**
  - [ ] RATE_LIMIT_ENABLED: true
  - [ ] Rate limit working (test with rapid requests)
  - [ ] Prevents API abuse

## 5.3 Monitoring & Logging

- [ ] **Sentry Configuration** (if used)
  - [ ] SENTRY_DSN set in Render environment
  - [ ] Errors captured in Sentry dashboard
  - [ ] Alerts configured for critical errors

- [ ] **Application Logs**
  - [ ] Check Render dashboard → Logs
  - [ ] No error messages visible
  - [ ] Normal startup logs present
  - [ ] No security warnings

---

# PHASE 6: LIVE LAUNCH (10 MINUTES)

## 6.1 Custom Domain Setup (Optional but Recommended)

### Frontend Domain
- [ ] **Vercel Domain Configuration**
  - [ ] Vercel Dashboard → Settings → Domains
  - [ ] Add custom domain: yourdomain.com
  - [ ] Add www subdomain: www.yourdomain.com
  - [ ] Copy DNS records provided by Vercel

- [ ] **Update DNS Records**
  - [ ] Login to domain registrar (GoDaddy, namecheap, etc.)
  - [ ] Add CNAME record for yourdomain.com → vercel.app domain
  - [ ] Add CNAME record for www → vercel.app domain
  - [ ] Wait for DNS propagation (5-48 hours)
  - [ ] Test: https://yourdomain.com loads correctly

### Backend Domain (Optional)
- [ ] **Render Domain** (if desired, Render provides custom domains)
  - [ ] Render Dashboard → Service → Settings
  - [ ] Custom domain setup (if available in plan)
  - [ ] Update FRONTEND environment variable if changed

## 6.2 Final Verification

- [ ] **Frontend Live**
  - [ ] Open https://yourdomain.com
  - [ ] Loads without errors
  - [ ] All features functional
  - [ ] API integration works

- [ ] **Backend Live**
  - [ ] API endpoint responding
  - [ ] Health check: 200 status
  - [ ] Database connected
  - [ ] All external services available

- [ ] **Business Ready**
  - [ ] Users can register
  - [ ] Users can log in
  - [ ] All core features work
  - [ ] No errors in logs

## 6.3 Go Live

- [ ] **Announce Launch**
  - [ ] Notify stakeholders
  - [ ] Share live URL with users
  - [ ] Enable new user registrations
  - [ ] Start monitoring

---

# PHASE 7: POST-LAUNCH MONITORING (30 MIN+)

## 7.1 Immediate Monitoring (First Hour)

- [ ] **Check Dashboard Status**
  - [ ] Vercel: No deployment errors
  - [ ] Render: Service healthy (green status)
  - [ ] Response times normal
  - [ ] Error rate: 0-0.5%

- [ ] **User Activity**
  - [ ] Monitor new user registrations
  - [ ] Check for API errors in logs
  - [ ] Verify transactions processing correctly
  - [ ] No critical errors reported

## 7.2 Continuous Monitoring (First 24 Hours)

- [ ] **Performance Metrics**
  - [ ] API response time < 100ms (p95)
  - [ ] Frontend page load < 3 seconds
  - [ ] Database query time < 50ms
  - [ ] Error rate remains < 0.5%

- [ ] **User Experience**
  - [ ] No CORS errors reported
  - [ ] Authentication flow working
  - [ ] Real-time updates operational
  - [ ] Payment processing successful (if applicable)

- [ ] **Log Analysis**
  - [ ] Review Render logs for warnings
  - [ ] Check Sentry for errors
  - [ ] Look for patterns in failures
  - [ ] Identify performance bottlenecks

## 7.3 Ongoing Operations

- [ ] **Daily Checks**
  - [ ] Health endpoints returning 200
  - [ ] Error rate monitoring
  - [ ] Database performance
  - [ ] User activity trends

- [ ] **Weekly Reviews**
  - [ ] Analyze logs for issues
  - [ ] Review error patterns
  - [ ] Update monitoring alerts
  - [ ] Plan optimizations

- [ ] **Monthly Operations**
  - [ ] Database maintenance
  - [ ] Dependency updates
  - [ ] Security review
  - [ ] Performance optimization

---

## ✅ Launch Success Criteria

All of the following must be true:

✅ Backend service running (green on Render)  
✅ Frontend deployed (live on Vercel)  
✅ Health endpoint: 200 response  
✅ API documentation accessible  
✅ User authentication working  
✅ Database connected and operational  
✅ Real-time updates functional  
✅ Error rate < 0.5%  
✅ No CORS errors  
✅ HTTPS enforced  
✅ All secrets secured  
✅ Monitoring configured  
✅ Response time < 100ms (p95)  

---

## 🔗 Quick Reference

| Component | Link | Status |
|-----------|------|--------|
| Render Backend | https://dashboard.render.com | ✅ |
| Vercel Frontend | https://vercel.com/dashboard | ✅ |
| MongoDB Atlas | https://account.mongodb.com | ✅ |
| Health Endpoint | https://cryptovault-api.onrender.com/health/ready | ✅ |
| API Docs | https://cryptovault-api.onrender.com/.api/docs | ✅ |
| Frontend | https://cryptovault-frontend.vercel.app | ✅ |

---

## 📞 Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails on Render | Check Python dependencies, Node version |
| API not reachable | Verify MONGO_URL, check Render logs |
| CORS errors | Update backend CORS_ORIGINS for frontend domain |
| WebSocket fails | Verify REACT_APP_WEBSOCKET_URL in Vercel |
| High error rate | Check Sentry, review logs, restart service |
| Slow response time | Check database indexes, enable Redis caching |

---

## 🎯 Next Steps After Launch

1. **Monitor Actively** (first 24 hours)
   - Observe user activity
   - Watch error rates
   - Track performance metrics

2. **Scale if Needed**
   - Upgrade Render plan if high traffic
   - Optimize database queries
   - Enable caching/CDN

3. **Continuous Improvements**
   - Gather user feedback
   - Fix reported issues
   - Optimize performance
   - Add new features

4. **Security Updates**
   - Monitor dependency vulnerabilities
   - Update packages regularly
   - Review access logs
   - Conduct security audits

---

**Status**: ✅ Ready for Live Business  
**Duration**: 1-2 hours from start to launch  
**Support**: All documentation included  

**Good luck with your live launch! 🚀**
