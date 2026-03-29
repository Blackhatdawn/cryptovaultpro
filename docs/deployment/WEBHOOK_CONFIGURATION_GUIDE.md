# 🔗 NOWPayments Webhook Configuration Guide

## Overview

This guide covers the complete setup and testing of NOWPayments webhooks for CryptoVault's deposit system.

---

## 📍 Webhook Endpoint

**Production Webhook URL:**
```
https://cryptovault-api.onrender.com/api/wallet/webhook/nowpayments
```

**Testing Endpoint:**
```
https://cryptovault-api.onrender.com/api/wallet/webhook/test
```

---

## 🔧 NOWPayments Dashboard Configuration

### Step 1: Access NOWPayments Dashboard

1. Log in to [NOWPayments Dashboard](https://account.nowpayments.io/)
2. Navigate to **Settings** → **API**

### Step 2: Configure IPN (Instant Payment Notification)

1. Find **IPN Settings** section
2. Set **IPN Callback URL**:
   ```
   https://cryptovault-api.onrender.com/api/wallet/webhook/nowpayments
   ```
3. Enable **Send IPN Notifications**
4. Copy your **IPN Secret** (you'll need this for signature verification)

### Step 3: Update Backend Environment Variables

Ensure these variables are set in your Render.com dashboard:

```bash
NOWPAYMENTS_API_KEY=<your-nowpayments-api-key>
NOWPAYMENTS_IPN_SECRET=<your-nowpayments-ipn-secret>
NOWPAYMENTS_SANDBOX=false
PUBLIC_API_URL=https://cryptovault-api.onrender.com
```

---

## 🧪 Testing Webhooks

### Test 1: Verify Endpoint Accessibility

```bash
curl -X POST https://cryptovault-api.onrender.com/api/wallet/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"test": "webhook connectivity"}'
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Webhook endpoint is accessible and working",
  "received": {
    "content_type": "application/json",
    "body_length": 30,
    "payload": {"test": "webhook connectivity"},
    "client_host": "..."
  }
}
```

### Test 2: Simulate NOWPayments Webhook

```bash
curl -X POST https://cryptovault-api.onrender.com/api/wallet/webhook/nowpayments \
  -H "Content-Type: application/json" \
  -H "x-nowpayments-sig: test-signature" \
  -d '{
    "payment_id": "test-123",
    "payment_status": "finished",
    "order_id": "DEP-test-12345678",
    "actually_paid": 100,
    "price_amount": 100,
    "price_currency": "usd",
    "pay_currency": "btc"
  }'
```

**Note:** This will fail signature verification in production, but will log the attempt.

### Test 3: Use NOWPayments Sandbox

1. Set `NOWPAYMENTS_SANDBOX=true` in Render environment variables
2. Use sandbox API key from NOWPayments dashboard
3. Create a test payment
4. Complete payment in sandbox
5. Check Render logs for webhook receipt

---

## 📊 Webhook Payload Format

NOWPayments sends webhooks with this structure:

```json
{
  "payment_id": "5077125051",
  "payment_status": "finished",
  "pay_address": "bc1q...",
  "price_amount": 100.00,
  "price_currency": "usd",
  "pay_amount": 0.001234,
  "pay_currency": "btc",
  "order_id": "DEP-abc123-def456",
  "order_description": "CryptoVault Deposit - $100",
  "purchase_id": "123456789",
  "outcome_amount": 100.00,
  "outcome_currency": "usd",
  "payin_extra_id": null,
  "actually_paid": 0.001234,
  "created_at": "2025-02-05T12:00:00.000Z",
  "updated_at": "2025-02-05T12:05:00.000Z"
}
```

### Payment Status Values

- `waiting` - Waiting for payment
- `confirming` - Payment received, waiting for confirmations
- `confirmed` - Payment confirmed
- `sending` - Sending to your account
- `partially_paid` - Partially paid
- `finished` - ✅ Payment complete (funds credited)
- `failed` - ❌ Payment failed
- `refunded` - Payment refunded
- `expired` - Payment expired

---

## 🔐 Security Features

### 1. Signature Verification

All webhooks are verified using HMAC-SHA512:

```python
signature = hmac.new(
    IPN_SECRET.encode('utf-8'),
    sorted_json.encode('utf-8'),
    hashlib.sha512
).hexdigest()
```

The signature is sent in the `x-nowpayments-sig` header.

### 2. Idempotency

Webhooks can be received multiple times. The system:
- Checks if webhook already processed
- Returns success without reprocessing
- Prevents duplicate credits

### 3. Order Validation

- Verifies order exists in database
- Checks user ownership
- Validates payment amounts

---

## 📝 Monitoring Webhooks

### Check Render Logs

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select `cryptovault-backend` service
3. Click **Logs** tab
4. Search for: `📬 NOWPayments webhook`

### Webhook Log Events

```
📬 NOWPayments webhook received from 1.2.3.4
✅ Webhook signature verified
📬 Processing webhook: Order DEP-... - Status: finished
💰 Processing successful payment: $100 for user abc-123
✅ Wallet updated: $500 → $600
✅ Deposit completed: DEP-... - $100 credited to user abc-123
```

### Error Log Events

```
❌ Invalid IPN signature received for payment: 5077125051
⚠️ Deposit not found for order: DEP-invalid
❌ JSON parsing error in webhook: Expecting value: line 1 column 1
```

---

## 🐛 Troubleshooting

### Issue 1: "Invalid signature"

**Cause:** IPN Secret mismatch or request body altered

**Fix:**
1. Verify `NOWPAYMENTS_IPN_SECRET` matches NOWPayments dashboard
2. Check logs for actual vs expected signature
3. Ensure webhook URL is exactly as configured

### Issue 2: "Order not found"

**Cause:** Order ID mismatch or deposit not created

**Fix:**
1. Check deposit was created before payment
2. Verify order_id format: `DEP-{user_id[:8]}-{uuid[:8]}`
3. Check database for deposit record

### Issue 3: "Webhook not received"

**Cause:** URL not accessible or incorrect

**Fix:**
1. Test endpoint accessibility (see Test 1 above)
2. Verify URL in NOWPayments dashboard
3. Check Render service is running (not sleeping)
4. Verify no firewall/rate limiting blocking NOWPayments IPs

### Issue 4: "Empty request body"

**Cause:** NOWPayments sending non-JSON or empty payload

**Fix:**
1. Check NOWPayments dashboard for webhook history
2. Enable debug logging in production temporarily
3. Contact NOWPayments support if persistent

---

## 🔄 Webhook Retry Logic

### NOWPayments Retry Behavior

- Retries on 5xx errors (server errors)
- Does NOT retry on 4xx errors (client errors)
- Exponential backoff: 1min, 5min, 15min, 1hr, 6hr
- Maximum 10 retry attempts

### Our Response Strategy

**Return 200 OK when:**
- Webhook processed successfully
- Order not found (prevents endless retries)
- Already processed (idempotent)

**Return 400 Bad Request when:**
- Invalid signature
- Missing required fields
- Invalid JSON

**Return 500 Internal Server Error when:**
- Database error
- Unexpected exception
- (Triggers retry from NOWPayments)

---

## 📈 Webhook Flow Diagram

```
NOWPayments → Webhook Sent
              ↓
         Render Backend
              ↓
    ┌─────────────────┐
    │ Verify Signature│
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ Parse Payload   │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ Find Deposit    │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │Check Idempotency│
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ Update Status   │
    └────────┬────────┘
             │
    (if status = finished)
             │
    ┌────────▼────────┐
    │ Credit Wallet   │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │Create Transaction│
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │   Notify User   │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │  Return 200 OK  │
    └─────────────────┘
```

---

## 🎯 Best Practices

1. **Always verify signatures** in production
2. **Log all webhook events** for audit trail
3. **Implement idempotency** to handle duplicate webhooks
4. **Return appropriate status codes** for retry behavior
5. **Monitor webhook failures** and investigate promptly
6. **Test in sandbox first** before production
7. **Keep IPN Secret secure** - never commit to git
8. **Handle all payment statuses** (not just finished)

---

## 📞 Support

### NOWPayments Support
- Email: support@nowpayments.io
- Telegram: @NOWPayments_support
- Dashboard: https://account.nowpayments.io/

### CryptoVault Backend Logs
- Dashboard: https://dashboard.render.com
- Service: cryptovault-backend
- Real-time logs available in Logs tab

---

## ✅ Checklist

Before going live:

- [ ] Webhook URL configured in NOWPayments dashboard
- [ ] IPN Secret set in backend environment variables
- [ ] PUBLIC_API_URL points to production backend
- [ ] Test endpoint returns successful response
- [ ] Sandbox payment flow tested end-to-end
- [ ] Logs showing webhook receipt and processing
- [ ] Production payment tested with real crypto
- [ ] Wallet credited correctly
- [ ] Transaction created in database
- [ ] User notified of successful deposit

---

**Last Updated:** 2025-02-05
**Status:** ✅ Production Ready
