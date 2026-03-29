# PHASE 1: Infrastructure Startup - Step-by-Step Guide

**Timeline**: 15-20 minutes  
**Goal**: Get all services running (MongoDB → Backend API → Frontend)

---

## Quick Start (Choose Your Platform)

### macOS / Linux

```bash
# Option 1: Start everything step-by-step (Recommended for first time)
./start-backend.sh

# Then in a new terminal:
cd frontend && pnpm dev --host 0.0.0.0 --port 5173
```

### Windows

```bash
# Option 1: Start backend
start-backend.bat

# Then in a new terminal:
cd frontend
pnpm dev --host 0.0.0.0 --port 5173
```

---

## STEP 1: Verify MongoDB is Running

MongoDB must be running for the backend API to start successfully.

### macOS (Homebrew)

```bash
# Check if MongoDB is running
brew services list | grep mongodb

# If not running, start it:
brew services start mongodb-community

# Verify connection:
mongosh --eval "db.version()"
```

**Expected Output**: Shows MongoDB version (e.g., "7.0.0")

### Linux (Ubuntu/Debian)

```bash
# Check status
sudo systemctl status mongod

# If not running, start it:
sudo systemctl start mongod

# Verify connection:
mongosh --eval "db.version()"
```

### Windows

```bash
# Check if MongoDB is running (look for mongod.exe in Task Manager)
# If not running, start MongoDB service:

# Option A: Using Services app
# 1. Press Win+R, type: services.msc
# 2. Find "MongoDB Server" or "mongod"
# 3. Right-click → Start

# Option B: Using Command Prompt (Admin)
net start MongoDB

# Verify connection:
mongosh --eval "db.version()"
```

### Docker

```bash
# If using Docker for MongoDB:
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Verify it's running:
docker ps | grep mongodb
```

**Checklist**:
- [ ] MongoDB is running
- [ ] `mongosh` or `mongo` connects successfully
- [ ] Version output shows (e.g., "7.0.0")

---

## STEP 2: Verify Backend Environment

The `.env` file should already be in place. Let's verify it's configured correctly:

```bash
cd backend

# Check if .env exists
ls -la .env

# Check critical variables are set
grep -E "MONGO_URL|ENVIRONMENT|PORT" .env
```

**Expected output** should show:
```
MONGO_URL=mongodb://localhost:27017/cryptovault_dev
ENVIRONMENT=development
BACKEND_PORT=8001
```

If `.env` is missing, create it:

```bash
cp .env.template .env

# Edit .env and verify these are set:
# MONGO_URL=mongodb://localhost:27017/cryptovault_dev
# ENVIRONMENT=development
# BACKEND_PORT=8001
```

---

## STEP 3: Install Python Dependencies (First Time Only)

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate it:
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi; print('✅ FastAPI installed')"
```

**Expected output**: `✅ FastAPI installed`

---

## STEP 4: Start Backend Server

### Using the provided startup script (Recommended)

```bash
# macOS/Linux
./start-backend.sh

# Windows
start-backend.bat
```

### Or manually with uvicorn:

```bash
cd backend

# Activate virtual environment if not already activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Start the server
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**Expected output** (should see these messages):

```
[v0] Backend Configuration Validated
✅ FastAPI app created
✅ CORS middleware configured
✅ Rate limiting configured
...
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete
```

**Test the backend is running**:

```bash
# In a new terminal:
curl http://localhost:8001/ping

# Expected response:
# {"status":"ok","message":"pong","timestamp":"2024-03-29T...","version":"1.0.0"}
```

---

## STEP 5: Verify Backend API Connection

Check that the API is accessible:

```bash
# Health check
curl http://localhost:8001/health

# Root endpoint
curl http://localhost:8001/

# API docs
open http://localhost:8001/api/docs
```

**Expected** - All endpoints should return valid JSON responses

---

## STEP 6: Start Frontend Development Server

In a **new terminal** (keep backend running in first terminal):

```bash
cd frontend

# Install dependencies if not already done
pnpm install

# Start dev server
pnpm dev --host 0.0.0.0 --port 5173
```

**Expected output**:

```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to access from other machines
```

---

## STEP 7: Verify Frontend API Connection

Open your browser to `http://localhost:5173`

Check the browser console for any errors. The app should:
- ✅ Load without errors
- ✅ Display the login page or dashboard
- ✅ Make successful API calls to the backend (check Network tab)
- ✅ No more `ECONNREFUSED` errors in console

---

## Troubleshooting

### Backend won't start: "ECONNREFUSED 127.0.0.1:27017"

**Problem**: MongoDB not running

**Solution**:
```bash
# macOS
brew services start mongodb-community

# Linux
sudo systemctl start mongod

# Windows - use Services app or:
net start MongoDB

# Docker
docker run -d -p 27017:27017 mongo:latest
```

### Backend won't start: "ModuleNotFoundError: No module named 'fastapi'"

**Problem**: Dependencies not installed

**Solution**:
```bash
cd backend
source venv/bin/activate  # macOS/Linux
# or venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Backend won't start: "Port 8001 is already in use"

**Problem**: Another process is using port 8001

**Solution**:
```bash
# macOS/Linux - find and kill process
lsof -i :8001
kill -9 <PID>

# Windows - find and kill process
netstat -ano | findstr :8001
taskkill /PID <PID> /F

# Or change port in backend/.env:
BACKEND_PORT=8002
```

### Frontend can't reach backend API

**Problem**: CORS or proxy configuration issue

**Solution**:
1. Verify backend is running: `curl http://localhost:8001/ping`
2. Check frontend is configured to use correct backend URL
3. Check browser console for CORS errors
4. Verify vite.config.ts proxy settings

### MongoDB connection fails

**Problem**: MongoDB connection string is incorrect

**Solution**:
```bash
# Test connection directly:
mongosh "mongodb://localhost:27017/cryptovault_dev"

# If using MongoDB Atlas instead:
mongosh "mongodb+srv://user:password@cluster.mongodb.net/cryptovault_dev"

# Update backend/.env with correct URL
MONGO_URL=<correct-connection-string>
```

---

## ✅ Phase 1 Complete!

Once all three services are running:

1. **MongoDB**: `mongosh` connects successfully
2. **Backend API**: `http://localhost:8001/health` returns 200 OK
3. **Frontend**: `http://localhost:5173` loads without errors
4. **Integration**: Frontend API calls work (check Network tab in DevTools)

**Next Steps**: Move to Phase 2 - Configuration Validation (See PHASE_2_EXECUTION_CHECKLIST.md)

