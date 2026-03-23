# CryptoVault PRD - Product Requirements Document

## Original Problem Statement
Build a comprehensive crypto exchange web application (CryptoVault) with features similar to Bybit, Coinbase, and Binance. The platform includes user authentication, live price tickers, wallet management, trading, staking, referrals, admin panel, and push notifications.

## Architecture
- **Frontend**: React + TypeScript + Vite + TailwindCSS + Framer Motion
- **Backend**: FastAPI (Python) + MongoDB Atlas
- **Auth**: JWT (access + refresh tokens via httpOnly Secure cookies)
- **Real-time**: Socket.IO WebSocket for live prices
- **Push**: Firebase Cloud Messaging (FCM)
- **Email**: SendGrid/SMTP with mock fallback
- **Cache**: In-memory (Redis disabled - free tier exhausted)

## What's Been Implemented

### Core Features (Complete)
- User registration/login with JWT + httpOnly cookies
- Admin panel with OTP authentication
- Live crypto price tickers via WebSocket
- Wallet management, trading orders, staking/earn products
- Price alerts system
- Multi-tier referral program (Bronze/Silver/Gold/Platinum)
- Firebase push notifications (live)
- Email service with graceful mock fallback
- 38 frontend pages, 24 backend routers

### Security Audit & Hardening (Feb 2026)
**Critical Fixes (C1-C6) - All Implemented:**
- C1: Admin JWT secret now HMAC-derived (independent from user secret)
- C2: CSRF secret upgraded to 64-byte random hex
- C3: JWT tokens now include jti, aud, and iss claims
- C4: Admin OTP uses secrets.choice (cryptographic randomness)
- C5: Token type validation enforced (refresh tokens rejected as access tokens)
- C6: All datetime.utcnow() replaced with datetime.now(timezone.utc)

**High-Severity Fixes (H1-H5) - All Implemented:**
- H1: Refresh token rotation (new refresh token on each refresh, old one blacklisted)
- H2: Session invalidation on password change (new tokens issued, old sessions expired)
- H3: Login error messages normalized (prevents account enumeration)
- H4: Login-specific rate limiting (global 60/min + account lockout)
- H5: Cookie Secure flag unified (always Secure=True)

**Additional Fixes:**
- Blacklist now checks token before refresh (replay protection)
- Logout blacklists tokens from both cookies and Authorization header
- Lazy DB access in blacklist module (prevents stale references)

### Deployment
- Gunicorn + Uvicorn workers configured for Render
- Successfully deployed to Render (confirmed by user)

## Known Issues
- **Email**: SendGrid/SMTP credentials invalid - using mock fallback
- **Redis**: Upstash free tier exhausted - using in-memory cache

## Pending (P2 - Medium Priority)
- M1-M10 medium severity items from security audit (documented in SECURITY_AUDIT_REPORT.md)
- Production VAPID key for web push
- User-configurable push notification preferences
- Session limit per user
- 2FA disable requires password re-confirmation
- Backup codes should be hashed before storage

## Test Credentials
- **User**: secaudit@test.com / SecAudit2026!
- **Admin**: admin@cryptovault.financial / CryptoAdmin2026! (OTP bypassed in dev)
