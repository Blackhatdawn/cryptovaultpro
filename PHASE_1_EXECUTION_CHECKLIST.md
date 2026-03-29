# PHASE 1: IMMEDIATE INFRASTRUCTURE FIXES - EXECUTION CHECKLIST
**Timeline**: 1-2 hours  
**Goal**: Get backend API server running on port 8001 and frontend connecting successfully

---

## ROOT CAUSE ANALYSIS

**Problem**: Frontend (Vite) tries to proxy API requests to `http://127.0.0.1:8001` but gets `ECONNREFUSED` errors

**Root Causes Identified**:
1. **Missing `.env` file** - Backend has no environment variables configured
2. **MongoDB not running** - Database not initialized locally
3. **Backend server not started** - No Python server process on port 8001
4. **Frontend proxy misconfigured** - May have incorrect backend URL

**Solution**: Start services in correct sequence: MongoDB → Backend API → Frontend Dev Server

---

## STEP 1: CREATE .ENV FILE ✅ DONE
**Status**: Environment file created at `/backend/.env`  
**Details**:
- Configured for local development
- Using localhost MongoDB
- Mock price service enabled
- Email configured with placeholder credentials
- All critical secrets set with dev-only values

**Next**: Verify or update for your environment

---

## STEP 2: SETUP MONGODB
**Effort**: 5-10 minutes

### Option A: Local MongoDB (Recommended for Dev)
```bash
# macOS (using Homebrew)
brew install mongodb-community
brew services start mongodb-community

# Ubuntu/Linux
sudo apt-get install mongodb
sudo systemctl start mongod

# Windows (using Homebrew on Windows or official installer)
# Download from: https://www.mongodb.com/try/download/community

# Verify it's running
mongo --version
mongosh --eval "db.version()"
```

**Expected Output**:
```
Connected to MongoDB
Server version: 6.x.x
```

### Option B: MongoDB Atlas (Cloud)
If you prefer cloud-hosted MongoDB:
1. Go to https://www.mongodb.com/cloud/atlas
2. Create free account
3. Create a cluster (M0 free tier)
4. Get connection string
5. Update `.env`: `MONGO_URL=<your-atlas-uri>`

### Option C: Docker
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

**Checklist**:
- [ ] MongoDB installed locally OR Atlas cluster created
- [ ] MongoDB running (`mongosh` connects successfully)
- [ ] `MONGO_URL` in `.env` points to correct instance
- [ ] Database connection tested

---

## STEP 3: INSTALL PYTHON DEPENDENCIES
**Effort**: 3-5 minutes

```bash
# Navigate to backend directory
cd /vercel/share/v0-project/backend

# Verify Python version (must be 3.8+)
python --version
# Output should be: Python 3.9.x or higher

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Verify FastAPI installed
python -c "import fastapi; print(f'FastAPI {fastapi.__version__} installed')"
```

**Expected Output**:
```
FastAPI 0.110.1 installed
Successfully installed 120+ packages
```

**Checklist**:
- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] All dependencies from `requirements.txt` installed
- [ ] No installation errors

---

## STEP 4: VERIFY BACKEND CONFIGURATION
**Effort**: 2-3 minutes

```bash
# From backend directory, test configuration loading
python -c "from config import settings, validate_startup_environment; print(f'Config loaded: {settings.environment} mode'); validate_startup_environment()"
```

**Expected Output**:
```
Config loaded: development mode
✅ All configuration validated
```

**If errors occur**, check:
1. `.env` file exists in `/backend` directory
2. All required variables are set (see PHASE_BY_PHASE_FIX_PLAN.md)
3. MongoDB URL is correct and accessible

**Checklist**:
- [ ] Config loads without errors
- [ ] Environment set to `development`
- [ ] Startup validation passes
- [ ] Database connection validated

---

## STEP 5: START BACKEND SERVER
**Effort**: 2-3 minutes

```bash
# From backend directory
# Option 1: Direct Python execution (recommended for development)
python server.py

# Option 2: Using start_server.py wrapper
python start_server.py

# Option 3: Using Gunicorn (production-like)
gunicorn server:app --workers 1 --bind 0.0.0.0:8001
```

**Expected Output** (FastAPI with Uvicorn):
```
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Application startup complete
✅ CryptoVault API Server Started
```

**Important Note**: Keep this terminal running! Backend must stay active for frontend to connect.

**Checklist**:
- [ ] Backend server starts without errors
- [ ] Server listening on port 8001
- [ ] Logs show "Application startup complete"
- [ ] No connection errors to MongoDB, Email, etc.

---

## STEP 6: TEST BACKEND API ENDPOINTS
**Effort**: 3-5 minutes  
**From a NEW terminal window** (keep backend running):

```bash
# Test 1: Health check endpoint
curl http://localhost:8001/ping
# Expected: {"status": "healthy"} or similar

# Test 2: API version check
curl http://localhost:8001/api/version/check
# Expected: JSON with version info

# Test 3: Check authentication (should fail gracefully)
curl http://localhost:8001/api/auth/me
# Expected: 401 Unauthorized (because we're not logged in)
# NOT: ECONNREFUSED error!

# Test 4: Check crypto data endpoint
curl http://localhost:8001/api/crypto
# Expected: JSON array with crypto prices (mock or real)
```

**Success Indicators**:
- All endpoints return responses (not ECONNREFUSED)
- Health check returns 200
- Auth returns 401 (expected for unauthenticated request)
- No "connection refused" errors

**Checklist**:
- [ ] `/ping` responds with 200
- [ ] `/api/version/check` returns version info
- [ ] `/api/auth/me` returns 401 (not 500 or connection error)
- [ ] `/api/crypto` returns price data
- [ ] No ECONNREFUSED errors

---

## STEP 7: INSTALL & START FRONTEND
**Effort**: 3-5 minutes  
**From a NEW terminal window**:

```bash
# Navigate to frontend directory
cd /vercel/share/v0-project/frontend

# Install dependencies
npm install
# OR if using pnpm
pnpm install
# OR if using yarn
yarn install

# Start development server
npm run dev
# Expected output:
# VITE v5.x.x  ready in 123 ms
# ➜  Local:   http://localhost:5173/
# ➜  press h to show help
```

**Frontend will start on**:
- Local: `http://localhost:5173/` (or similar)
- Check the terminal output for exact URL

**Checklist**:
- [ ] Frontend dependencies installed
- [ ] Dev server starts successfully
- [ ] No errors in console
- [ ] Application loads in browser

---

## STEP 8: TEST FRONTEND-BACKEND INTEGRATION
**Effort**: 2-3 minutes

### In Browser Console (F12):
```javascript
// Check if frontend can reach backend
fetch('http://localhost:8001/api/auth/me')
  .then(r => r.json())
  .then(d => console.log('Backend response:', d))
  .catch(e => console.error('Error:', e.message))
```

**Expected Outcome**:
```javascript
// Should see something like:
// Backend response: {error: "missing_token"} 
// OR similar error response

// NOT: NetworkError or connection refused!
```

### In Browser Network Tab:
1. Open DevTools (F12)
2. Go to Network tab
3. Refresh page
4. Look for API calls
5. **Should see**: HTTP responses (200, 401, etc.)
6. **NOT Should see**: ECONNREFUSED errors or pending requests

**Checklist**:
- [ ] Frontend loads in browser
- [ ] No console errors about port 8001 connection
- [ ] Network tab shows API responses (not failures)
- [ ] Price data loading (or showing mock data)
- [ ] No "proxy error" messages in server logs

---

## STEP 9: VERIFY ALL CRITICAL FEATURES
**Effort**: 5 minutes

### Test Critical Flows:
```javascript
// 1. Check if price data is loading
fetch('http://localhost:8001/api/crypto')
  .then(r => r.json())
  .then(d => console.log('Prices loaded:', d.length, 'assets'))

// 2. Check health status
fetch('http://localhost:8001/ping')
  .then(r => r.text())
  .then(d => console.log('Health:', d))

// 3. Check WebSocket (if available)
const ws = new WebSocket('ws://localhost:8001/ws')
ws.onopen = () => console.log('WebSocket connected')
ws.onerror = (e) => console.error('WebSocket error:', e.message)
```

**Checklist**:
- [ ] Price data loading without errors
- [ ] Health endpoint accessible
- [ ] WebSocket connecting (if enabled)
- [ ] No 8001 connection errors anywhere

---

## PHASE 1 SUCCESS CRITERIA ✅

### All of these must be true:
1. ✅ Backend server running on port 8001
2. ✅ MongoDB connected and accessible
3. ✅ Frontend loads in browser without errors
4. ✅ Network tab shows API responses (no ECONNREFUSED)
5. ✅ Price data or mock data visible in frontend
6. ✅ Health check endpoint responds
7. ✅ No "proxy error" messages in logs
8. ✅ Frontend can connect to backend APIs

---

## TROUBLESHOOTING GUIDE

### Error: "ECONNREFUSED 127.0.0.1:8001"
**Cause**: Backend server not running  
**Fix**:
```bash
# Go to backend directory and start server:
cd backend
python server.py
# Keep terminal open!
```

### Error: "Cannot find module 'fastapi'"
**Cause**: Dependencies not installed  
**Fix**:
```bash
cd backend
pip install -r requirements.txt
```

### Error: "MongoError: connect ECONNREFUSED 127.0.0.1:27017"
**Cause**: MongoDB not running  
**Fix**:
```bash
# macOS
brew services start mongodb-community

# Ubuntu
sudo systemctl start mongod

# Or start with Docker
docker run -d -p 27017:27017 mongo:latest
```

### Error: "Address already in use: 127.0.0.1:8001"
**Cause**: Something else using port 8001  
**Fix**:
```bash
# Find process using port 8001
lsof -i :8001
# Kill it and restart
kill -9 <PID>
python server.py
```

### Frontend blank or not loading
**Cause**: Wrong Vite proxy configuration  
**Fix**: Check `frontend/vite.config.ts` has:
```typescript
proxy: {
  '/api': 'http://localhost:8001',
  '/ping': 'http://localhost:8001'
}
```

### Emails not sending
**Cause**: Invalid SMTP credentials  
**Fix**: Update `.env`:
```
EMAIL_SERVICE=smtp
SMTP_HOST=mail.spacemail.com
SMTP_PORT=465
SMTP_USERNAME=<actual-username>
SMTP_PASSWORD=<actual-password>
```

---

## NEXT STEPS AFTER PHASE 1

Once all checkboxes are complete:
1. ✅ Celebrate! Infrastructure is working
2. 👉 **Proceed to PHASE 2**: Environment Configuration
3. Document any configuration you changed
4. Keep this terminal setup running for development

---

## FILES CREATED/MODIFIED

| File | Status | Purpose |
|------|--------|---------|
| `backend/.env` | ✅ Created | Configuration for local dev |
| `PHASE_BY_PHASE_FIX_PLAN.md` | ✅ Created | Overall strategy |
| `PHASE_1_EXECUTION_CHECKLIST.md` | ✅ Created | This file - detailed steps |

---

## QUICK REFERENCE - START EVERYTHING

Once set up once, here's how to start everything for development:

```bash
# Terminal 1: MongoDB
brew services start mongodb-community  # macOS
# OR
docker run -d -p 27017:27017 mongo:latest  # Docker

# Terminal 2: Backend API
cd /vercel/share/v0-project/backend
source venv/bin/activate
python server.py

# Terminal 3: Frontend Dev Server
cd /vercel/share/v0-project/frontend
npm run dev

# Open browser to http://localhost:5173 (or URL shown in Terminal 3)
```

---

**Ready to start? Begin with STEP 2: SETUP MONGODB**
