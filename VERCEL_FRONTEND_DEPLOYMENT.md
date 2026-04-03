# 🚀 Vercel Frontend Deployment - Production Guide

**Status**: ✅ Enterprise Ready | **Platform**: Vercel.com | **Framework**: React/Next.js

---

## 📋 Quick Start (5 Minutes)

### Prerequisites
- ✅ Vercel account created (https://vercel.com)
- ✅ Frontend repository pushed to GitHub
- ✅ Backend API deployed on Render
- ✅ Custom domain registered (optional but recommended)

### Deployment Steps

1. **Import Project to Vercel**
   - Login to Vercel: https://vercel.com/dashboard
   - Click: "Add New..." → "Project"
   - Select: GitHub → Choose your repository
   - Select: Frontend directory (if monorepo)

2. **Configure Project**
   ```
   Framework: React / Next.js (auto-detected)
   Build Command: npm run build (or pnpm build)
   Output Directory: build (or .next for Next.js)
   Install Command: npm install (or pnpm install)
   ```

3. **Environment Variables**
   ```
   REACT_APP_API_URL=https://your-api.onrender.com
   REACT_APP_WEBSOCKET_URL=wss://your-api.onrender.com
   ```
   (Set these in Vercel Dashboard → Settings → Environment Variables)

4. **Deploy**
   - Click: "Deploy"
   - Wait for build completion
   - Verify: https://your-project.vercel.app

5. **Custom Domain (Optional)**
   - Vercel → Settings → Domains
   - Add your domain
   - Update DNS records

---

## 🔐 Environment Variables Setup

### Production Variables

```env
# API Configuration
REACT_APP_API_URL=https://your-api.onrender.com
REACT_APP_WEBSOCKET_URL=wss://your-api.onrender.com
REACT_APP_API_TIMEOUT=30000

# Feature Flags
REACT_APP_ENABLE_ANALYTICS=true
REACT_APP_ENABLE_CRASH_REPORTING=true
REACT_APP_ENABLE_PERFORMANCE_MONITORING=true

# Third-Party Services
REACT_APP_GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX
REACT_APP_SENTRY_DSN=https://key@sentry.io/project

# Optional
REACT_APP_ENVIRONMENT=production
REACT_APP_VERSION=2.0.0
```

### Development Variables (for local testing)

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WEBSOCKET_URL=ws://localhost:8000
```

---

## 📊 Vercel Configuration Details

### Project Settings
```
Framework: React / Next.js
Build Command: npm run build
Output Directory: build
Node Version: 18.x LTS
```

### Auto-Deploy
```
✅ Deploy on every push to main branch
✅ Preview deployments for pull requests
✅ Instant rollback available
✅ Environment-specific settings
```

### Domains
```
Default: your-project.vercel.app (auto)
Custom: yourdomain.com (recommended)
Wildcard: *.yourdomain.com (optional)
```

---

## ✅ Verification Checklist

### Post-Deployment
- [ ] Site is live and loading
- [ ] No build errors in Vercel logs
- [ ] Environment variables are set
- [ ] API URL points to Render backend
- [ ] Navigation works
- [ ] API calls succeed

### Frontend Features
- [ ] Authentication flow works
- [ ] Login/registration functional
- [ ] API calls to backend succeed
- [ ] WebSocket real-time updates work
- [ ] Error handling displays properly
- [ ] Loading states show correctly

### Performance
- [ ] Page load time < 3 seconds (mobile)
- [ ] Lighthouse score > 80 (desktop)
- [ ] No console errors
- [ ] API responses < 100ms

### Security
- [ ] HTTPS enforced (automatic on Vercel)
- [ ] No hardcoded secrets in code
- [ ] API calls use correct headers
- [ ] CORS errors resolved (backend CORS_ORIGINS updated)

---

## 🔗 Frontend-Backend Integration

### API Connection
```javascript
// Environment variable should point to Render
const API_URL = process.env.REACT_APP_API_URL;

// Example API call
fetch(`${API_URL}/api/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
})
```

### WebSocket Connection
```javascript
// Real-time updates
const WEBSOCKET_URL = process.env.REACT_APP_WEBSOCKET_URL;
const socket = io(WEBSOCKET_URL, {
  auth: { token: authToken }
});
```

### Error Handling
```javascript
// Set REACT_APP_API_URL in Vercel environment variables
// The backend returns standardized error format:
// { error: { code: "...", message: "...", details: {...} } }
```

---

## 🔧 Common Issues & Solutions

### Issue: Build Fails
**Error**: `npm install failed` or `build failed`
**Causes**:
1. Missing dependencies
2. Node version mismatch
3. TypeScript errors

**Solutions**:
```bash
# 1. Check package.json dependencies
npm install

# 2. Verify Node version in Vercel settings matches local
# Vercel uses Node 18.x by default

# 3. Fix TypeScript errors
npm run type-check
```

### Issue: API Calls Return 404 or Connection Refused
**Error**: `Cannot reach backend API`
**Cause**: REACT_APP_API_URL not set correctly
**Solution**:
```bash
# 1. Verify REACT_APP_API_URL in Vercel Dashboard
# Should be: https://your-api.onrender.com

# 2. Test endpoint:
curl https://your-api.onrender.com/health/ready

# 3. Check backend CORS_ORIGINS includes your frontend domain
```

### Issue: CORS Errors
**Error**: `Access to XMLHttpRequest blocked by CORS`
**Solution**: Update backend environment variable:
```bash
# On Render service
CORS_ORIGINS=https://your-domain.vercel.app,https://yourdomain.com

# Then redeploy Render service
```

### Issue: WebSocket Connection Failed
**Error**: `WebSocket connection failed`
**Cause**: REACT_APP_WEBSOCKET_URL incorrect
**Solution**:
```bash
# 1. Verify WebSocket URL in Vercel environment
# Should be: wss://your-api.onrender.com

# 2. Ensure backend has Socket.IO enabled
# Check backend/socketio_server.py
```

### Issue: Blank Page or Hydration Errors
**Error**: Page loads but nothing displays
**Causes**:
1. API call timing issue
2. State management problem
3. Build output issue

**Solutions**:
```bash
# 1. Check browser console for errors
# 2. Verify Vercel build logs
# 3. Test locally first: npm start
# 4. Check API responses: use browser DevTools Network tab
```

---

## 📈 Performance Optimization

### Build Optimization
```bash
# In package.json
"build": "react-scripts build && npm run optimize"

# Or if using Next.js
"build": "next build"
```

### API Calls
```javascript
// Add request timeout
const timeout = new Promise((_, reject) =>
  setTimeout(() => reject(new Error('Timeout')), 30000)
);

Promise.race([fetch(url), timeout])
```

### Caching
```javascript
// Cache API responses to reduce calls
const cache = new Map();

function cachedFetch(url, timeout = 3600000) {
  if (cache.has(url) && Date.now() - cache.get(url).time < timeout) {
    return Promise.resolve(cache.get(url).data);
  }
  return fetch(url).then(r => {
    cache.set(url, { data: r, time: Date.now() });
    return r;
  });
}
```

---

## 🔐 Security Hardening for Production

### Before Going Live
- [ ] All secrets in Vercel environment (not in Git)
- [ ] No API keys in source code
- [ ] HTTPS enforced (automatic)
- [ ] CSP headers configured
- [ ] CORS validation on backend

### Environment Variables
```bash
# ❌ NEVER commit these
API_URL=https://api.example.com
JWT_TOKEN=secret-token

# ✅ DO: Set in Vercel Dashboard
# Settings → Environment Variables
```

### Frontend Security
- [ ] Validate all API responses
- [ ] Escape user input
- [ ] Use HTTPS only
- [ ] Enable Content Security Policy
- [ ] Keep dependencies updated

---

## 🚀 Deployment Workflow

### First Deployment
```
1. Create Vercel account
2. Import GitHub repository
3. Set environment variables
4. Configure build settings
5. Deploy (automatic)
6. Test health endpoints
7. Add custom domain
8. Test frontend-backend integration
```

### Updates & Redeployment
```
1. Push code to main branch
2. Vercel automatically deploys
3. Check deployment status
4. Test preview URL
5. Merge to main to deploy to production
```

### Instant Rollback
```
1. Vercel Dashboard → Project → Deployments
2. Find previous working deployment
3. Click "Promote to Production"
4. Verify frontend-backend sync
```

---

## 📞 Support Resources

### Vercel Documentation
- [Vercel Docs](https://vercel.com/docs)
- [Environment Variables](https://vercel.com/docs/environment-variables)
- [Troubleshooting](https://vercel.com/docs/troubleshooting)
- [Framework Guides](https://vercel.com/guides)

### Frontend Debugging
- [React Debugging](https://react.dev/learn/react-developer-tools)
- [DevTools Guide](https://www.google.com/chrome/devtools/)
- [Network Tab Guide](https://developer.chrome.com/docs/devtools/network/)

### Integration
- [Backend API](./RENDER_BACKEND_DEPLOYMENT.md)
- [API Documentation](https://your-api.onrender.com/.api/docs)

---

## 🎯 Success Criteria

✅ Site is live and accessible  
✅ All pages load without errors  
✅ API calls to backend succeed  
✅ Authentication flow works  
✅ WebSocket updates work in real-time  
✅ Performance metrics good (Lighthouse > 80)  
✅ No CORS errors  
✅ Secure (HTTPS enforced, no exposed secrets)  
✅ Fast deployment and rollback  

---

## 🔗 Quick Links

| Action | Link |
|--------|------|
| Vercel Dashboard | https://vercel.com/dashboard |
| Project Settings | Vercel → Project → Settings |
| Environment Vars | Vercel → Settings → Environment Variables |
| Deployments | Vercel → Deployments |
| Frontend Site | https://your-project.vercel.app |
| Backend API | https://your-api.onrender.com |

---

**Last Updated**: April 3, 2026  
**Status**: ✅ Production Ready  
**Platform**: Vercel (Edge Network)  
**Deployment**: Automatic from GitHub  

---

**Previous Step**: [Render Backend Deployment Guide](./RENDER_BACKEND_DEPLOYMENT.md)  
**Next Step**: [Production Deployment Checklist](./PRODUCTION_DEPLOYMENT_CHECKLIST.md)
