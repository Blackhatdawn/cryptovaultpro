# CryptoVault Frontend - Vercel Deployment Guide

This guide provides step-by-step instructions for deploying the CryptoVault frontend to Vercel for production.

## Prerequisites

- ✅ Backend is live at: `https://cryptovault-api.onrender.com`
- ✅ Vercel account with GitHub connection
- ✅ Domain configured (optional but recommended)

## 🚀 Quick Deployment

### 1. Connect Repository to Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click "Add New..." → "Project"
3. Import your GitHub repository
4. Select the `frontend` directory as the root directory

### 2. Configure Build Settings

Vercel should auto-detect these settings, but verify:

```bash
Framework Preset: Vite
Build Command: pnpm build
Output Directory: dist
Install Command: pnpm install --frozen-lockfile
```

### 3. Set Environment Variables

In your Vercel project settings, add these environment variables:

#### Required Variables
```bash
# Optional if using Vercel rewrites + /api/config (recommended)
VITE_API_BASE_URL=https://cryptovault-api.onrender.com
VITE_APP_NAME=CryptoVault
VITE_APP_VERSION=1.0.0
VITE_NODE_ENV=production
VITE_ENABLE_SENTRY=true
```

#### Optional (Recommended)
```bash
# Sentry Error Tracking (get from https://sentry.io)
# Prefer backend PUBLIC_SENTRY_DSN via /api/config; this is a fallback.
VITE_SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# Google Analytics (if needed)
VITE_GA_TRACKING_ID=G-XXXXXXXXXX
```

### 4. Deploy

Click "Deploy" - Vercel will automatically build and deploy your application.

## 🔧 Advanced Configuration

### Custom Domain

1. In Vercel project settings → "Domains"
2. Add your custom domain
3. Update DNS records as instructed
4. SSL certificate will be automatically provisioned

### Environment-Specific Deployments

- **Production**: Deploy from `main` branch
- **Staging**: Deploy from `staging` branch (optional)
- **Preview**: All pull requests get automatic preview deployments

## 🛡️ Security Configuration

### Content Security Policy (CSP)

The `vercel.json` file includes comprehensive security headers:

- ✅ XSS Protection
- ✅ Content Type Options
- ✅ Frame Options (DENY)
- ✅ Referrer Policy
- ✅ CSP with allowed domains for API and external resources

### CORS Configuration

The backend API (`cryptovault-api.onrender.com`) should allow your frontend domain:

```python
# Backend CORS configuration should include:
allowed_origins = [
    \"https://your-domain.vercel.app\",
    \"https://your-custom-domain.com\",
]
```

## 📊 Monitoring & Error Tracking

### Sentry Integration

1. **Create Sentry Project**:
   - Go to [Sentry.io](https://sentry.io)
   - Create new project for React
   - Copy the DSN

2. **Configure Environment Variables**:
   ```bash
   VITE_SENTRY_DSN=your-sentry-dsn-here
   VITE_ENABLE_SENTRY=true
   ```

3. **Features Included**:
   - ✅ Automatic error capture
   - ✅ User context tracking
   - ✅ Performance monitoring
   - ✅ Session replay
   - ✅ User feedback collection

### Vercel Analytics (Built-in)

Vercel provides built-in analytics for:
- Page views
- Core Web Vitals
- User demographics
- Traffic sources

Enable in Project Settings → Analytics

## 🔄 CI/CD Pipeline

### Automatic Deployments

- ✅ **Production**: Auto-deploy from `main` branch
- ✅ **Preview**: Auto-deploy for pull requests
- ✅ **Branch Deployments**: Deploy any branch manually

### Build Optimizations

The build includes:
- ✅ Code splitting by vendor and page
- ✅ Tree shaking for unused code
- ✅ Asset optimization and compression
- ✅ Progressive Web App features
- ✅ Source maps for debugging (dev only)

## 🔍 Performance Optimization

### Bundle Splitting

```javascript
// Optimized chunks for better loading:
- vendor.js (React, React-DOM)
- web3-vendor.js (Ethers.js)
- ui-vendor.js (Radix UI components)
- charts-vendor.js (Chart.js, Lightweight Charts)
- data-vendor.js (React Query, Axios)
- sentry-vendor.js (Sentry SDK)
- pages/*.js (Individual page components)
- core.js (Contexts and hooks)
```

### Caching Strategy

- ✅ **Static Assets**: 1 year cache with immutable flag
- ✅ **HTML**: No cache (always fresh)
- ✅ **API Calls**: 30-second stale-while-revalidate

## 🔧 Troubleshooting

### Common Issues

#### 1. **Build Fails**
```bash
# Check for TypeScript errors
pnpm lint
pnpm build

# Common fixes:
- Update all dependencies
- Check for missing environment variables
- Verify API endpoints are accessible
```

#### 2. **API Calls Fail**
```bash
# Verify environment variables
echo $VITE_API_BASE_URL

# Check CORS configuration on backend
# Verify backend is accessible from browser
```

#### 3. **Blank Page After Deploy**
```bash
# Check browser console for errors
# Verify all environment variables are set
# Check Sentry error reports
```

### Debug Tools

1. **Vercel Function Logs**: Check deployment logs
2. **Browser DevTools**: Check network and console
3. **Sentry**: Monitor real-time errors
4. **Vercel Analytics**: Monitor performance metrics

## 📋 Pre-Deployment Checklist

### Code Quality
- [ ] All TypeScript errors resolved
- [ ] ESLint warnings addressed
- [ ] Build completes without warnings
- [ ] All tests passing (if applicable)

### Configuration
- [ ] Environment variables configured
- [ ] API endpoints verified
- [ ] Sentry DSN configured
- [ ] Custom domain configured (if applicable)

### Security
- [ ] CSP policies reviewed
- [ ] Security headers configured
- [ ] HTTPS enabled
- [ ] API CORS configured correctly

### Performance
- [ ] Bundle size optimized (< 1MB initial load)
- [ ] Images optimized
- [ ] Lazy loading implemented
- [ ] Core Web Vitals tested

### Monitoring
- [ ] Sentry error tracking enabled
- [ ] Analytics configured
- [ ] Vercel monitoring enabled
- [ ] Health checks configured

## 🎯 Post-Deployment Verification

### 1. **Functionality Tests**
- [ ] Home page loads correctly
- [ ] User authentication works
- [ ] API calls successful
- [ ] Real-time features working (WebSocket)
- [ ] Trading interface functional

### 2. **Performance Tests**
- [ ] Page load time < 3 seconds
- [ ] Core Web Vitals in good range
- [ ] Mobile performance optimized
- [ ] All lazy-loaded routes work

### 3. **Security Verification**
- [ ] Security headers present
- [ ] HTTPS enforced
- [ ] CSP violations checked
- [ ] No sensitive data exposed

## 🆘 Support

If you encounter issues during deployment:

1. **Check Vercel Deployment Logs**: Look for specific error messages
2. **Review Environment Variables**: Ensure all required variables are set
3. **Test API Connectivity**: Verify backend is accessible
4. **Monitor Sentry**: Check for real-time errors
5. **Contact Support**: Reach out with specific error messages and logs

---

**Last Updated**: January 2025
**Version**: 1.0.0
**Status**: Production Ready ✅