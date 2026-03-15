# Firebase Push Notifications - Setup Guide

## Step-by-Step Firebase Setup

### Step 1: Create a Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **"Create a project"** (or **"Add project"**)
3. Enter project name: `CryptoVault` (or any name)
4. Disable Google Analytics (optional for this use case)
5. Click **"Create project"** → Wait for it to finish → Click **"Continue"**

### Step 2: Enable Cloud Messaging
1. In your Firebase project, go to **Project Settings** (gear icon top-left)
2. Click the **"Cloud Messaging"** tab
3. Under **Web Push certificates**, click **"Generate key pair"**
4. Copy the **VAPID key** — you'll need this for the frontend

### Step 3: Register a Web App
1. Go to **Project Settings** → **General** tab
2. Under "Your apps", click the **web icon** `</>`
3. Enter app nickname: `CryptoVault Web`
4. Click **"Register app"**
5. Copy the `firebaseConfig` object — you'll need `apiKey`, `projectId`, `messagingSenderId`, `appId`

### Step 4: Get Service Account Credentials (for backend)
1. Go to **Project Settings** → **Service accounts** tab
2. Click **"Generate new private key"**
3. Download the JSON file
4. Either:
   - **Option A**: Copy the entire JSON content and set it as `FIREBASE_CREDENTIALS_JSON` environment variable
   - **Option B**: Save the file to `/app/backend/firebase-credentials.json`

### Step 5: Update Environment Variables

**Backend** (`/app/backend/.env`):
```
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"your-project",...}
# OR
FIREBASE_CREDENTIALS_PATH=/app/backend/firebase-credentials.json
```

**Frontend** (`/app/frontend/.env`):
```
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id
VITE_FIREBASE_VAPID_KEY=your-vapid-key
```

### Step 6: Restart Backend
```bash
sudo supervisorctl restart backend
```

### Verification
After setup, FCM will switch from MOCK mode to LIVE mode automatically.
Check push status: `GET /api/push/status`
Test notification: `POST /api/push/test`

---

## Current Status
- **Backend**: FCM service implemented with mock fallback
- **Frontend**: Service worker + notification permission flow ready
- **Endpoints**:
  - `POST /api/push/register-token` - Register device for push
  - `DELETE /api/push/unregister-token` - Opt out
  - `POST /api/push/test` - Send test notification
  - `GET /api/push/status` - Check if push is enabled
