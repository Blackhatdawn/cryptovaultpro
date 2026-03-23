# CryptoVault Authentication Security Audit Report

**Date**: February 2026
**Scope**: Full authentication lifecycle (signup, login, session management, token handling, admin auth, password reset, 2FA, CSRF)
**Standard**: OWASP Top 10 (2021), OWASP ASVS L2

---

## Executive Summary

The CryptoVault authentication system has a solid foundation with bcrypt password hashing, JWT-based sessions via httpOnly cookies, account lockout protection, audit logging, and CSRF middleware. However, **6 Critical**, **9 High**, and **10 Medium** severity vulnerabilities were identified that must be addressed before production deployment.

---

## Vulnerability Report

### CRITICAL (P0) - Must Fix Before Production

| # | Vulnerability | File(s) | OWASP Category |
|---|---|---|---|
| C1 | Admin JWT secret trivially derived from user JWT secret | `admin_auth.py:28` | A2: Cryptographic Failures |
| C2 | CSRF secret is weak (`auth-fix-119`) | `.env:28` | A2: Cryptographic Failures |
| C3 | No `jti` (JWT ID) claim - token revocation by ID impossible | `auth.py:59-71` | A7: Identification Failures |
| C4 | Admin OTP uses non-cryptographic `random.choices` | `admin_auth.py:108` | A2: Cryptographic Failures |
| C5 | Token type NOT validated in `get_current_user_id` - refresh token accepted as access token | `dependencies.py:94` | A1: Broken Access Control |
| C6 | `datetime.utcnow()` used throughout (deprecated, caused OTP bug already) | `auth.py`, `routers/auth.py` | A4: Insecure Design |

### HIGH (P1) - Fix Before Production

| # | Vulnerability | File(s) | OWASP Category |
|---|---|---|---|
| H1 | No refresh token rotation - stolen refresh tokens valid for full 7 days | `routers/auth.py:576-605` | A7: Identification Failures |
| H2 | No session invalidation on password change | `routers/auth.py:546-572` | A7: Identification Failures |
| H3 | Login error messages leak account state (locked vs invalid vs not found) | `routers/auth.py:342-399` | A1: Broken Access Control |
| H4 | No login-specific rate limiting (only global 60/min) | `routers/auth.py:305` | A7: Identification Failures |
| H5 | Cookie Secure flag inconsistent between endpoints | `routers/auth.py:71 vs 595` | A5: Security Misconfiguration |
| H6 | No `aud` (audience) claim in JWT tokens | `auth.py:59-71` | A7: Identification Failures |
| H7 | Refresh token not bound to IP/device | `routers/auth.py:576-605` | A7: Identification Failures |
| H8 | Blacklist stores full JWT strings (inefficient, unbounded growth) | `blacklist.py` | A4: Insecure Design |
| H9 | Multiple valid password reset tokens can coexist | `routers/auth.py:729-790` | A7: Identification Failures |

### MEDIUM (P2) - Address in Next Sprint

| # | Vulnerability | File(s) | OWASP Category |
|---|---|---|---|
| M1 | `User(**user_doc)` deserializes full doc including password_hash | `routers/auth.py:340` | A3: Injection |
| M2 | No audit log for failed email verification attempts | `routers/auth.py:609` | A9: Logging Failures |
| M3 | Verification code is 6 digits with 24-hour validity (brute-forceable) | `email_service.py` | A7: Identification Failures |
| M4 | CSRF token in httpOnly cookie conflicts with SPA double-submit pattern | `server.py:946` | A5: Security Misconfiguration |
| M5 | Blacklist module imports `db_connection` at module level (stale ref risk) | `blacklist.py:13` | A4: Insecure Design |
| M6 | No session limit per user (unlimited concurrent sessions) | N/A | A7: Identification Failures |
| M7 | 2FA disable doesn't require password re-confirmation | `routers/auth.py:933-949` | A1: Broken Access Control |
| M8 | Backup codes generated without being hashed | `routers/auth.py:903` | A2: Cryptographic Failures |
| M9 | Admin bootstrap creates random password that's effectively lost | `admin_auth.py:244` | A5: Security Misconfiguration |
| M10 | No `last_failed_attempt` cooldown tracking per IP (only per account) | `routers/auth.py` | A7: Identification Failures |

---

## Remediation Plan (What Will Be Implemented Now)

### Phase 1: Critical Fixes (C1-C6)
1. **C1**: Generate independent admin JWT secret (separate env var or derived via HMAC with distinct key material)
2. **C2**: Generate strong CSRF secret (64-byte random hex)
3. **C3**: Add `jti` claim to all JWT tokens; use jti for blacklist keys
4. **C4**: Replace `random.choices` with `secrets.choice` in admin OTP
5. **C5**: Validate token `type` == "access" in `get_current_user_id`
6. **C6**: Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)`

### Phase 2: High-Severity Fixes (H1-H5)
7. **H1**: Implement refresh token rotation (issue new refresh token on each refresh)
8. **H2**: Invalidate all sessions on password change (bump a `password_changed_at` timestamp, validate in token decode)
9. **H3**: Normalize login error responses to prevent enumeration
10. **H4**: Add per-IP and per-email rate limiting on login endpoint
11. **H5**: Unify cookie Secure flag logic into `set_auth_cookies` helper

### Phase 3: Medium Fixes (Deferred)
Documented for next sprint. See individual items above.

---

## What's Already Good

- Bcrypt with 12 rounds for password hashing
- httpOnly cookies for token storage (XSS-resistant)
- Account lockout after 5 failed attempts (15-minute window)
- Password complexity policy enforced server-side
- Audit logging for auth events
- Background email sending (non-blocking)
- CSRF double-submit pattern (needs refinement)
- Security headers middleware (HSTS, X-Frame-Options, CSP, etc.)
- Token blacklisting on logout
- Fraud detection data collection on signup
