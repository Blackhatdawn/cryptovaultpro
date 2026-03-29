# CryptoVault Pro - Phase-by-Phase Fix Plan
**Date**: March 29, 2026  
**Priority**: Resolve critical blockers preventing application launch

---

## PHASE 1: IMMEDIATE INFRASTRUCTURE FIXES (1-2 hours)
### Root Cause Analysis
**Current Problem**: Backend API server (port 8001) not running
- Frontend (Vite) trying to proxy requests to http://127.0.0.1:8001
- All API calls failing with ECONNREFUSED errors
- Application non-functional in current state

### Phase 1 Actions (IN ORDER):

#### Step 1.1: Verify Backend Dependencies
- [ ] Check `backend/requirements.txt` for all Python dependencies
- [ ] Verify Python version (likely 3.9+)
- [ ] Check for environment variables needed (JWT_SECRET, MONGO_URL, etc.)

#### Step 1.2: Start Backend Server
- [ ] Navigate to `/backend` directory
- [ ] Run: `pip install -r requirements.txt` (if not already installed)
- [ ] Verify `.env` file exists with all critical variables:
  - `ENVIRONMENT` = local/staging
  - `JWT_SECRET` = test key
  - `ADMIN_JWT_SECRET` = test key
  - `MONGO_URL` = test MongoDB URI
  - Email service variables
- [ ] Start server with: `python backend/server.py` OR `python backend/start_server.py`
- [ ] Verify server starts on port 8001

#### Step 1.3: Verify Frontend Build
- [ ] Check `frontend/package.json` for build scripts
- [ ] Verify `frontend/vite.config.ts` has correct proxy settings
- [ ] Confirm frontend dev server proxy points to `http://localhost:8001`

#### Step 1.4: Test Integration
- [ ] Frontend should start without connection errors
- [ ] Health check: `GET /ping` should return 200
- [ ] Auth check: `GET /api/auth/me` should return 401 (no auth) instead of ECONNREFUSED

---

## PHASE 2: ENVIRONMENT CONFIGURATION (1-2 hours)
### Objective: Complete all required environment variables

#### Step 2.1: Identify Missing Variables
- [ ] Read `backend/.env.template` or `.env.example`
- [ ] List all REQUIRED variables (not optional)
- [ ] Cross-reference with `backend/config.py`
- [ ] Identify which need external setup (Redis, Email, etc.)

#### Step 2.2: Critical Variables Setup
**These MUST be configured before production**:
```
Secrets (generate new):
- JWT_SECRET (32+ chars, random)
- ADMIN_JWT_SECRET (32+ chars, random)
- CSRF_SECRET (32+ chars, random)

Database:
- MONGO_URL (test or production)
- DB_NAME (cryptovault_production)

Email Service:
- EMAIL_SERVICE (smtp or resend)
- SMTP_HOST/PORT/USERNAME/PASSWORD (if using SMTP)
- EMAIL_FROM (verified sender)

Cache (Optional for Phase 1, Required for Phase 3):
- UPSTASH_REDIS_REST_URL (if using Redis)
- UPSTASH_REDIS_REST_TOKEN (if using Redis)

APIs:
- COINCAP_API_KEY (price feeds)
- NOWPAYMENTS_API_KEY (payment processing)
```

#### Step 2.3: Validation Script
- [ ] Create `.env.test` file
- [ ] Run backend health checks
- [ ] Verify all connections (DB, Email, APIs)

---

## PHASE 3: EMAIL SERVICE VALIDATION (2-3 hours)
### Objective: Ensure email delivery works end-to-end

#### Step 3.1: SMTP Configuration Testing
- [ ] Verify SMTP credentials in `backend/email_service.py`
- [ ] Test connection to mail server
- [ ] Confirm sender email is whitelisted

#### Step 3.2: End-to-End Email Test
- [ ] Create test signup flow
- [ ] Verify verification email arrives within 10 seconds
- [ ] Test verification link works
- [ ] Check that emails don't go to spam

#### Step 3.3: Setup Email Monitoring
- [ ] Configure delivery tracking
- [ ] Set up alerts for <95% success rate
- [ ] Document fallback email providers

---

## PHASE 4: REDIS CACHE SETUP (1-2 hours)
### Objective: Enable production-grade caching

#### Step 4.1: Upstash Redis Setup
- [ ] Create Upstash account (if not exists)
- [ ] Create Redis database (free tier: 10GB)
- [ ] Retrieve REST URL and token
- [ ] Add to environment variables

#### Step 4.2: Cache Configuration
- [ ] Test Redis connection in `backend/redis_cache.py`
- [ ] Verify price cache with 45s TTL
- [ ] Monitor cache hit rates (target >80%)

#### Step 4.3: Performance Validation
- [ ] Benchmark: Price requests with/without cache
- [ ] Confirm <50ms response time (cache hit)
- [ ] Verify data persistence on app restart

---

## PHASE 5: COMPREHENSIVE TESTING (2-3 hours)
### Objective: Validate critical user flows

#### Step 5.1: Smoke Tests
- [ ] Signup → Verification → Login flow
- [ ] Check portfolio page loads
- [ ] Test trading form submit
- [ ] Verify wallet operations
- [ ] Test 2FA if enabled

#### Step 5.2: API Tests
- [ ] Run `backend/tests/test_critical_endpoints.py`
- [ ] Verify all health checks pass
- [ ] Test error handling for edge cases

#### Step 5.3: Admin Dashboard
- [ ] Login as admin
- [ ] Verify all admin panels load
- [ ] Test KYC/AML controls
- [ ] Check user management operations

---

## PHASE 6: PRODUCTION DEPLOYMENT PREP (3-4 hours)
### Objective: Ready application for production launch

#### Step 6.1: Security Hardening
- [ ] Verify HTTPS enforced
- [ ] Confirm CORS settings are locked down
- [ ] Check rate limiting active
- [ ] Verify geo-blocking configured
- [ ] Confirm AML screening enabled

#### Step 6.2: Monitoring & Alerts
- [ ] Configure Sentry error tracking
- [ ] Setup performance monitoring
- [ ] Create alert rules for critical errors
- [ ] Document monitoring dashboard

#### Step 6.3: Documentation
- [ ] Create runbook for common issues
- [ ] Document deployment process
- [ ] List critical configuration items
- [ ] Create incident response guide

#### Step 6.4: Final Checklist
- [ ] All P0 blockers resolved
- [ ] All P1 features completed
- [ ] Critical tests passing (>95% success rate)
- [ ] Monitoring & alerts active
- [ ] Documentation complete
- [ ] Backup strategy documented

---

## EXECUTION TIMELINE

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| Phase 1: Infrastructure | 1-2 hrs | Now | +2hrs |
| Phase 2: Environment | 1-2 hrs | +2hrs | +4hrs |
| Phase 3: Email | 2-3 hrs | +4hrs | +7hrs |
| Phase 4: Redis | 1-2 hrs | +7hrs | +9hrs |
| Phase 5: Testing | 2-3 hrs | +9hrs | +12hrs |
| Phase 6: Deployment Prep | 3-4 hrs | +12hrs | +16hrs |
| **TOTAL** | **10-16 hours** | | |

---

## SUCCESS CRITERIA

✅ **Phase 1 Complete** when:
- Backend server running on port 8001
- Frontend connects without ECONNREFUSED errors
- Health endpoint responds with 200

✅ **Phase 2 Complete** when:
- All required environment variables configured
- All external services responding
- Configuration validation passes

✅ **Phase 3 Complete** when:
- Test email arrives within 10 seconds
- Verification link works correctly
- 99%+ email delivery success rate

✅ **Phase 4 Complete** when:
- Redis connection verified
- Cache hit rate >80%
- Price response time <50ms

✅ **Phase 5 Complete** when:
- All critical user flows work end-to-end
- API tests pass with >95% success rate
- Admin dashboard fully functional

✅ **Phase 6 Complete** when:
- All security controls active
- Monitoring & alerts configured
- Ready for production deployment

---

## NEXT STEPS

1. **Execute Phase 1 immediately** - Get application running
2. **Verify backend.server.py configuration** - Check startup requirements
3. **Review backend/.env.template** - Understand all variables needed
4. **Start backend server** - Get API responding
5. **Test frontend connectivity** - Verify proxy works

**PROCEED TO PHASE 1 EXECUTION**
