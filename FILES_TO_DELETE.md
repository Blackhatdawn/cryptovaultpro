# 🧹 Cleanup - Files to Delete

These files are now obsolete and should be removed from the repository to keep production clean and maintainable.

**Completed By**: Automated Cleanup Script (April 3, 2026)

---

## 🗂️ Root Directory Files to Delete

Remove these outdated documentation files from the root directory:

```bash
# Outdated phase documentation (28 files total)
rm -f 00_READ_ME_FIRST.txt
rm -f APPLICATION_UPDATE_ANALYSIS.md
rm -f BACKEND_DEPLOYMENT_COMPLETE.md
rm -f BACKEND_HARDENING_SESSION_SUMMARY.md
rm -f DELIVERABLES_SUMMARY.md
rm -f FILE_INVENTORY.md
rm -f FINAL_CLEANUP_STATUS.md
rm -f FIREBASE_SETUP_GUIDE.md
rm -f IMPLEMENTATION_STATUS.md
rm -f ORGANIZATION_CLEANUP_COMPLETE.md
rm -f PREPARATION_COMPLETE.txt
rm -f PRODUCTION_DEPLOYMENT_FINAL.md
rm -f PRODUCTION_LAUNCH_READINESS.md
rm -f PROJECT_COMPLETION_PLAN.md
rm -f QUICK_LINKS.md
rm -f README_EXECUTION_PLAN.md
rm -f SECURITY_AUDIT_REPORT.md
rm -f START_HERE.md
rm -f STEP_BY_STEP_EXECUTION_SUMMARY.md
rm -f SYSTEM_SYNC_REPORT.md
rm -f VISUAL_ROADMAP.txt
rm -f PHASE_1_*.* PHASE_2_*.* PHASE_3_*.*
rm -f PHASE_BY_PHASE_FIX_PLAN.md

# Keep these in root
✅ Keep: README.md (main documentation)
✅ Keep: START_HERE_FINAL.md (rename to START_HERE.md)
✅ Keep: PRODUCTION_DEPLOYMENT_CHECKLIST.md (new main guide)
✅ Keep: RENDER_BACKEND_DEPLOYMENT.md (new backend guide)
✅ Keep: VERCEL_FRONTEND_DEPLOYMENT.md (new frontend guide)
✅ Keep: PRODUCTION_READY.md (new overview)
✅ Keep: FRONTEND_BACKEND_INTEGRATION.md (API integration)
✅ Keep: render.yaml (Render config)
✅ Keep: vercel.json (Vercel config)
✅ Keep: docker-compose.yml (for local dev reference)
✅ Keep: Dockerfile.* (for reference)
✅ Keep: package.json, pnpm-lock.yaml
✅ Keep: .github/ directory (CI/CD config)
```

---

## 🔧 Backend Directory Files to Delete

Remove these files from `backend/` directory:

```bash
# Fly.io specific files
rm -f backend/fly.toml
rm -f backend/Dockerfile.fly
rm -f backend/FLY_SECRETS_GUIDE.md
rm -f backend/set-fly-secrets.sh
rm -f backend/deploy-fly.sh
rm -f backend/verify-fly-deployment.sh

# Outdated deployment documentation
rm -f backend/DEPLOYMENT_GUIDE.md
rm -f backend/DEPLOY_COMMANDS.sh
rm -f backend/deploy-complete.sh  
rm -f backend/EMAIL_PROVIDER_ALTERNATIVES.md
rm -f backend/PRODUCTION_HARDENING.md

# Keep these in backend
✅ Keep: requirements.txt (Python dependencies)
✅ Keep: server.py (FastAPI application)
✅ Keep: config.py (Configuration)
✅ Keep: startup.py (Health checks - created)
✅ Keep: error_handler.py (Error handling - created)
✅ Keep: Dockerfile (for local dev/reference)
✅ Keep: .env.example (updated for Render/Vercel)
✅ Keep: All Python source files (routers/, services/, etc.)
✅ Keep: All Python test files
✅ Keep: All middleware files
✅ Keep: .env (local config, NOT in Git)
```

---

## 📋 Scripts to Keep in Workspace

These scripts are still useful for development/reference:

```bash
✅ Keep: backend/run_server.py (local development)
✅ Keep: backend/start_server.py (server startup)
✅ Keep: backend/database_init.py (initial setup)
✅ Keep: scripts/ directory (if contains useful utilities)
✅ Keep: start-backend.sh (development reference)
✅ Keep: production_start.sh (can be updated)
```

---

## 🚀 Why These Deletions

| Files | Reason | Status |
|-------|--------|--------|
| Fly.io files | Platform no longer supported | Use Render only |
| Phase docs | Development phase complete | Use production guides |
| Old guides | Outdated/superseded | Use new Render+Vercel guides |
| Generic deployment | Not platform-specific | Use Render/Vercel specific guides |
| Email alternatives | Removed for simplicity | Use .env.example |

---

## ✅ Cleanup Verification

After deletion, verify the repository structure:

```bash
# Root should have:
ls -la *.md | grep -E "(PRODUCTION|RENDER|VERCEL|README)"

# Output should show:
# PRODUCTION_DEPLOYMENT_CHECKLIST.md ✅
# RENDER_BACKEND_DEPLOYMENT.md ✅
# VERCEL_FRONTEND_DEPLOYMENT.md ✅
# PRODUCTION_READY.md ✅
# FRONTEND_BACKEND_INTEGRATION.md ✅
# README.md ✅

# Backend should have:
ls -la backend/ | grep -E "\.py|\.txt|\.example" | wc -l
# Should show mostly .py files + requirements.txt + .env.example
```

---

## 🔒 Keep in .gitignore

Ensure these are NEVER committed:

```
.env                    # Local secrets
.env.local              # Local overrides
*.pyc                   # Python cache
__pycache__/            # Python cache dir
.DS_Store               # macOS files
node_modules/           # Frontend deps (also in frontend/)
.venv/                  # Virtual environment
*.egg-info/             # Package info
.pytest_cache/          # Test cache
```

---

## 📊 Final Structure

After cleanup, directory structure should be:

```
cryptovaultpro/
├── README.md
├── START_HERE_FINAL.md
├── PRODUCTION_READY.md ← New overview
├── PRODUCTION_DEPLOYMENT_CHECKLIST.md ← Main deployment guide
├── RENDER_BACKEND_DEPLOYMENT.md ← Backend specific
├── VERCEL_FRONTEND_DEPLOYMENT.md ← Frontend specific
├── FRONTEND_BACKEND_INTEGRATION.md (kept)
├── package.json (frontend)
├── render.yaml (Render config)
├── vercel.json (Vercel config)
├── frontend/
│   ├── package.json
│   ├── vercel.json (if exists)
│   └── ... (React app)
├── backend/
│   ├── requirements.txt
│   ├── server.py
│   ├── config.py
│   ├── startup.py (new)
│   ├── error_handler.py (new)
│   ├── Dockerfile
│   ├── .env.example (updated)
│   └── ... (Python source)
├── docs/
│   └── ... (any existing docs)
└── ... (other directories)
```

---

## 🎯 Success Criteria

Cleanup is complete when:

✅ Root directory has only essential .md files (6-8 total)  
✅ No PHASE_* files remain  
✅ No Fly.io files in backend/  
✅ No outdated deployment guides  
✅ .env files NOT in Git  
✅ Repository is clean and maintainable  
✅ Production deployment docs are clear  

---

## 📝 Optional Cleanup

These are optional to keep/delete:

```bash
# Could delete (if not needed):
- docker-compose.yml (if only using cloud platforms)
- Dockerfile.* (if only using cloud platforms)
- scripts/ (if no useful utilities)
- test_reports/ (cleanup old reports)
- _legacy_archive/ (if truly legacy)

# Better to keep (for reference):
- Dockerfile (useful for understanding structure)
- docker-compose.yml (helps developers understand architecture)
- scripts/ (may contain useful utilities)
- docs/ (external documentation)
```

---

## 🔗 After Cleanup

Once cleanup is complete, developers should:

1. **Read**: [PRODUCTION_READY.md](./PRODUCTION_READY.md) - Overview
2. **Follow**: [PRODUCTION_DEPLOYMENT_CHECKLIST.md](./PRODUCTION_DEPLOYMENT_CHECKLIST.md) - Deploy process
3. **Reference**: [RENDER_BACKEND_DEPLOYMENT.md](./RENDER_BACKEND_DEPLOYMENT.md) - Backend details
4. **Reference**: [VERCEL_FRONTEND_DEPLOYMENT.md](./VERCEL_FRONTEND_DEPLOYMENT.md) - Frontend details

---

**Cleanup Status**: ✅ Ready for Implementation  
**Impact**: Professional, clean repository structure  
**Result**: Simplified deployment process for live business  

---

## 🚀 Next Step

Execute cleanup script:
```bash
# From repository root
bash scripts/cleanup.sh  # If exists

# OR manually delete files listed above
```

Then verify: All production guides are in place and clear ✅
