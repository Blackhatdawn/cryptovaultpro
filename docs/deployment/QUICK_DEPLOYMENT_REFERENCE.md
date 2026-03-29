# 🚀 Quick Deployment Reference Card

## Immediate Action Required

### 1️⃣ Update Vercel Environment Variable (CRITICAL)

```
Variable: VITE_API_BASE_URL
Old Value: https://coinbase-love.fly.dev
New Value: https://cryptovault-api.onrender.com
```

**How to Update:**
1. Go to https://vercel.com/dashboard
2. Select your project
3. Settings → Environment Variables
4. Edit `VITE_API_BASE_URL`
5. Save and redeploy

---

### 2️⃣ Configure NOWPayments Webhook (CRITICAL)

```
Webhook URL: https://cryptovault-api.onrender.com/api/wallet/webhook/nowpayments
```

**How to Configure:**
1. Go to https://account.nowpayments.io/
2. Settings → API → IPN Settings
3. Set "IPN Callback URL" to above URL
4. Enable "Send IPN Notifications"
5. Save changes

---

### 3️⃣ Verify Render Environment Variables

Check these are set in Render dashboard:

```bash
PUBLIC_API_URL=https://cryptovault-api.onrender.com
NOWPAYMENTS_API_KEY=<your-nowpayments-api-key>
NOWPAYMENTS_IPN_SECRET=<your-nowpayments-ipn-secret>
NOWPAYMENTS_SANDBOX=false
```

---

## Testing Commands

### Test Backend Health
```bash
curl https://cryptovault-api.onrender.com/ping
```

### Test Webhook Endpoint
```bash
curl -X POST https://cryptovault-api.onrender.com/api/wallet/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": "verification"}'
```

### Run Full Verification
```bash
./verify_deployment.sh
```

---

## What Was Fixed

✅ Frontend now points to correct backend URL  
✅ Webhook URL now uses backend URL (not frontend)  
✅ Enhanced webhook payload handling  
✅ Added signature verification  
✅ Implemented idempotency protection  
✅ Improved error handling & logging  
✅ Added webhook testing endpoint  

---

## Files Modified

### Frontend
- `/app/frontend/.env.production` - Fixed API URL

### Backend
- `/app/backend/.env` - Updated PUBLIC_API_URL
- `/app/backend/routers/wallet.py` - Enhanced webhook handler
- `/app/backend/server.py` - Added webhook header to CORS

### Documentation
- `/app/WEBHOOK_CONFIGURATION_GUIDE.md` - Complete setup guide
- `/app/SYSTEM_FIXES_SUMMARY.md` - Detailed fix documentation
- `/app/verify_deployment.sh` - Automated testing script

---

## Success Indicators

After deployment, you should see:

1. ✅ Frontend loads without errors
2. ✅ Users can register/login
3. ✅ Deposits can be created
4. ✅ Webhook test endpoint returns success
5. ✅ Render logs show webhook receipt
6. ✅ Deposits credit wallet correctly

---

## Monitoring

### Check Logs
```bash
# Render Dashboard → cryptovault-backend → Logs
# Search for: "📬 NOWPayments webhook"
```

### Log Indicators
- 📬 = Webhook received
- ✅ = Success
- ❌ = Error
- ⚠️ = Warning
- 💰 = Payment processing

---

## Support

📚 Full Documentation: `/app/WEBHOOK_CONFIGURATION_GUIDE.md`  
🔧 Fix Summary: `/app/SYSTEM_FIXES_SUMMARY.md`  
✅ Test Script: `./verify_deployment.sh`

---

**Status:** ✅ Ready to Deploy  
**Priority:** 🔴 Critical - Deploy ASAP
