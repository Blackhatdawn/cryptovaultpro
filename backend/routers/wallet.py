"""Wallet and deposit management endpoints.

Fund Segregation Notes:
- Hot Wallet: Holds a small amount of funds for immediate withdrawals and P2P transfers.
  Connected to payment processors (NOWPayments) for real-time operations.
- Cold Wallet: Majority of funds stored offline for security.
  Accessed only for large withdrawals (>$10,000) or treasury operations.
  Cold wallet integration will require:
  1. Multi-signature scheme (2-of-3 admin keys)
  2. Hardware Security Module (HSM) integration
  3. Scheduled batch processing (daily/weekly)
  4. Manual override with audit trail

Hot/Cold Wallet Balance Thresholds:
- Hot wallet target: 10% of total assets or $100,000 (whichever is lower)
- Auto-sweep: Move excess hot wallet funds to cold storage daily
- Auto-refill: Top up hot wallet from cold storage when balance < 5%

TODO: Implement cold wallet integration with hardware signing
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import uuid
import logging

from dependencies import get_current_user_id, get_db, get_limiter
from nowpayments_service import nowpayments_service, PaymentStatus
from config import settings
from services.transactions_utils import broadcast_transaction_event
from email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wallet", tags=["wallet"])


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class DepositRequest(BaseModel):
    amount: float
    currency: str = "btc"  # Pay currency (BTC, ETH, etc.)


class WithdrawRequest(BaseModel):
    amount: float
    currency: str
    address: str


# ============================================
# HELPER FUNCTIONS
# ============================================

async def log_audit(db, user_id: str, action: str, resource: Optional[str] = None, 
                    ip_address: Optional[str] = None, details: Optional[dict] = None):
    """Log audit event."""
    from models import AuditLog
    
    logger.info(
        f"Audit log: {action}",
        extra={
            "type": "audit_log",
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "ip_address": ip_address
        }
    )
    
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        ip_address=ip_address,
        details=details
    )
    await db.get_collection("audit_logs").insert_one(audit_log.dict())


# ============================================
# WALLET BALANCE ENDPOINTS
# ============================================

@router.get("/balance")
async def get_wallet_balance(
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get user's wallet balance."""
    wallets_collection = db.get_collection("wallets")
    
    wallet = await wallets_collection.find_one({"user_id": user_id})
    
    if not wallet:
        # Create default wallet
        wallet = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "balances": {"USD": 0.0},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        await wallets_collection.insert_one(wallet)
    
    return {
        "wallet": {
            "balances": wallet.get("balances", {"USD": 0.0}),
            "updated_at": wallet.get("updated_at", datetime.utcnow()).isoformat()
        }
    }


# ============================================
# DEPOSIT ENDPOINTS
# ============================================

@router.post("/deposit/create")
async def create_deposit(
    data: DepositRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db),
    limiter = Depends(get_limiter)
):
    """
    Create a crypto deposit invoice.
    Uses NOWPayments integration.
    """
    if not settings.feature_deposits_enabled:
        raise HTTPException(status_code=503, detail="Deposits are currently disabled")

    # Validate amount
    if data.amount < 10:
        raise HTTPException(status_code=400, detail="Minimum deposit is $10")
    
    if data.amount > 100000:
        raise HTTPException(status_code=400, detail="Maximum deposit is $100,000")
    
    # Validate currency
    valid_currencies = ["btc", "eth", "usdt", "usdc", "ltc", "bnb", "sol"]
    if data.currency.lower() not in valid_currencies:
        raise HTTPException(status_code=400, detail=f"Invalid currency. Supported: {', '.join(valid_currencies)}")
    
    # Generate unique order ID
    order_id = f"DEP-{user_id[:8]}-{str(uuid.uuid4())[:8]}"
    
    # Create payment via NOWPayments
    try:
        # IPN callback URL for webhook notifications (use backend API URL, not frontend)
        backend_url = settings.public_api_url or settings.app_url
        ipn_callback_url = f"{backend_url}/api/wallet/webhook/nowpayments"
        success_url = f"{settings.app_url}/dashboard?deposit=success"
        cancel_url = f"{settings.app_url}/dashboard?deposit=cancelled"
        
        # Get user email for receipt
        users_collection = db.get_collection("users")
        user = await users_collection.find_one({"id": user_id})
        customer_email = user.get("email") if user else None
        
        payment_result = await nowpayments_service.create_payment(
            price_amount=data.amount,
            price_currency="usd",
            pay_currency=data.currency.lower(),
            order_id=order_id,
            order_description=f"CryptoVault Deposit - ${data.amount}",
            ipn_callback_url=ipn_callback_url,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email
        )
        
        if not payment_result.get("success"):
            raise HTTPException(
                status_code=500, 
                detail=payment_result.get("error", "Failed to create payment")
            )
        
        # Store deposit record
        deposits_collection = db.get_collection("deposits")
        deposit_record = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "order_id": order_id,
            "payment_id": payment_result.get("payment_id"),
            "amount": data.amount,
            "currency": "USD",
            "pay_currency": data.currency.upper(),
            "pay_amount": payment_result.get("pay_amount"),
            "pay_address": payment_result.get("pay_address"),
            "status": "pending",
            "mock": payment_result.get("mock", False),
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1),
            "updated_at": datetime.utcnow()
        }
        await deposits_collection.insert_one(deposit_record)
        
        # Log audit
        await log_audit(
            db, user_id, "DEPOSIT_INITIATED",
            resource=order_id,
            ip_address=request.client.host,
            details={"amount": data.amount, "currency": data.currency}
        )
        
        # Send Telegram notification to admin
        try:
            from services.telegram_bot import telegram_bot
            await telegram_bot.notify_deposit_created(
                user_id=user_id,
                user_email=customer_email or "Unknown",
                amount=data.amount,
                currency=data.currency,
                order_id=order_id,
                payment_id=payment_result.get("payment_id")
            )
        except Exception as e:
            logger.warning(f"Failed to send Telegram notification: {e}")
        
        logger.info(f"✅ Deposit created: {order_id} for ${data.amount}")
        
        return {
            "success": True,
            "orderId": order_id,
            "paymentId": payment_result.get("payment_id"),
            "amount": data.amount,
            "currency": data.currency.upper(),
            "payAddress": payment_result.get("pay_address"),
            "payAmount": payment_result.get("pay_amount"),
            "expiresAt": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "qrCode": payment_result.get("qr_code"),
            "mock": payment_result.get("mock", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Deposit creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create deposit")


@router.get("/deposit/{order_id}")
async def get_deposit_status(
    order_id: str,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get status of a specific deposit."""
    deposits_collection = db.get_collection("deposits")
    
    deposit = await deposits_collection.find_one({
        "order_id": order_id,
        "user_id": user_id
    })
    
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    
    # Refresh status from NOWPayments if not mock
    if not deposit.get("mock") and deposit.get("payment_id"):
        try:
            status_result = await nowpayments_service.get_payment_status(deposit["payment_id"])
            if status_result and "payment_status" in status_result:
                new_status = status_result["payment_status"]
                if new_status != deposit["status"]:
                    await deposits_collection.update_one(
                        {"order_id": order_id},
                        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
                    )
                    deposit["status"] = new_status
        except Exception as e:
            logger.warning(f"Failed to refresh deposit status: {e}")
    
    return {
        "deposit": {
            "orderId": deposit["order_id"],
            "amount": deposit["amount"],
            "currency": deposit["currency"],
            "payCurrency": deposit["pay_currency"],
            "payAmount": deposit.get("pay_amount"),
            "payAddress": deposit.get("pay_address"),
            "status": deposit["status"],
            "createdAt": deposit["created_at"].isoformat(),
            "expiresAt": deposit.get("expires_at", "").isoformat() if deposit.get("expires_at") else None
        }
    }


@router.get("/deposits")
async def get_deposit_history(
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get user's deposit history."""
    deposits_collection = db.get_collection("deposits")
    
    deposits = await deposits_collection.find(
        {"user_id": user_id}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    total = await deposits_collection.count_documents({"user_id": user_id})
    
    return {
        "deposits": [
            {
                "orderId": d["order_id"],
                "amount": d["amount"],
                "currency": d["currency"],
                "payCurrency": d["pay_currency"],
                "status": d["status"],
                "createdAt": d["created_at"].isoformat()
            }
            for d in deposits
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


# ============================================
# WEBHOOK ENDPOINTS
# ============================================

@router.post("/webhook/nowpayments")
async def nowpayments_webhook(
    request: Request,
    db = Depends(get_db)
):
    """
    Handle NOWPayments IPN (Instant Payment Notification) webhook.
    This is called by NOWPayments when payment status changes.
    
    Enterprise-grade webhook handling:
    - Signature verification for security
    - Proper content-type handling
    - Comprehensive error handling and logging
    - Idempotent processing
    """
    try:
        # Log webhook receipt
        logger.info(f"📬 NOWPayments webhook received from {request.client.host}")
        
        # Get raw body for signature verification (must be done before parsing)
        body = await request.body()
        
        # Check content-type (should be application/json)
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            logger.warning(f"Unexpected content-type: {content_type}")
            # Continue anyway - some webhook providers don't set proper content-type
        
        # Get signature header
        signature = request.headers.get("x-nowpayments-sig", "")
        
        # Parse payload first to check if it's valid JSON
        import json
        try:
            if not body:
                logger.error("Empty webhook body received")
                raise HTTPException(status_code=400, detail="Empty request body")
            
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook payload: {e}")
            # Log raw body for debugging (truncate if too long)
            body_preview = body.decode('utf-8', errors='ignore')[:200]
            logger.error(f"Raw body preview: {body_preview}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Verify signature (only if signature is provided)
        if signature:
            if not nowpayments_service.verify_ipn_signature(body, signature):
                logger.warning(f"❌ Invalid IPN signature received for payment: {payload.get('payment_id')}")
                raise HTTPException(status_code=400, detail="Invalid signature")
            logger.info("✅ Webhook signature verified")
        else:
            logger.warning("⚠️ No signature provided - processing anyway (development mode)")
        
        # Log full payload for debugging
        logger.info(f"Webhook payload: {json.dumps(payload, indent=2)}")
        
        payment_id = payload.get("payment_id")
        payment_status = payload.get("payment_status")
        order_id = payload.get("order_id")
        actually_paid = payload.get("actually_paid", 0)
        
        # Validate required fields
        if not payment_id or not payment_status or not order_id:
            logger.error(f"Missing required fields in webhook payload: {payload}")
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        logger.info(f"📬 Processing webhook: Order {order_id} - Status: {payment_status} - Payment ID: {payment_id}")
        
        # Send webhook received notification to admin
        try:
            from services.telegram_bot import telegram_bot
            await telegram_bot.notify_webhook_received(
                order_id=order_id,
                payment_status=payment_status,
                payment_id=payment_id
            )
        except Exception as e:
            logger.warning(f"Failed to send webhook Telegram notification: {e}")
        
        # Find deposit record
        deposits_collection = db.get_collection("deposits")
        deposit = await deposits_collection.find_one({"order_id": order_id})
        
        if not deposit:
            logger.warning(f"⚠️ Deposit not found for order: {order_id}")
            # Return 200 to acknowledge receipt (prevents retries for invalid orders)
            return {"status": "ignored", "reason": "Order not found", "order_id": order_id}
        
        # Check if already processed (idempotency)
        if deposit.get("status") == payment_status and deposit.get("webhook_processed"):
            logger.info(f"ℹ️ Webhook already processed for order: {order_id}")
            return {"status": "already_processed", "order_id": order_id}
        
        # Update deposit status
        await deposits_collection.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "status": payment_status,
                    "actually_paid": actually_paid,
                    "webhook_processed": True,
                    "webhook_received_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # If payment is finished/confirmed, credit the user's wallet
        if payment_status in PaymentStatus.SUCCESS_STATUSES:
            wallets_collection = db.get_collection("wallets")
            user_id = deposit["user_id"]
            amount = deposit["amount"]
            
            logger.info(f"💰 Processing successful payment: ${amount} for user {user_id}")
            
            # Update or create wallet
            wallet = await wallets_collection.find_one({"user_id": user_id})
            if wallet:
                current_balance = wallet.get("balances", {}).get("USD", 0)
                new_balance = current_balance + amount
                await wallets_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "balances.USD": new_balance,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                logger.info(f"✅ Wallet updated: ${current_balance} → ${new_balance}")
            else:
                await wallets_collection.insert_one({
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "balances": {"USD": amount},
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                })
                logger.info(f"✅ New wallet created with balance: ${amount}")
            
            # Create transaction record
            transactions_collection = db.get_collection("transactions")
            deposit_transaction = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": "deposit",
                "amount": amount,
                "currency": "USD",
                "status": "completed",
                "reference": order_id,
                "description": f"Deposit via {deposit['pay_currency']}",
                "created_at": datetime.utcnow()
            }
            await transactions_collection.insert_one(deposit_transaction)
            await broadcast_transaction_event(user_id, deposit_transaction)
            
            # Log audit
            await log_audit(
                db, user_id, "DEPOSIT_COMPLETED",
                resource=order_id,
                details={
                    "amount": amount,
                    "payment_status": payment_status,
                    "payment_id": payment_id,
                    "actually_paid": actually_paid
                }
            )
            
            logger.info(f"✅ Deposit completed: {order_id} - ${amount} credited to user {user_id}")
            
            # Send completion notification to admin
            try:
                from services.telegram_bot import telegram_bot
                users_collection = db.get_collection("users")
                user = await users_collection.find_one({"id": user_id})
                user_email = user.get("email", "Unknown") if user else "Unknown"
                
                # Get updated wallet balance
                wallet = await wallets_collection.find_one({"user_id": user_id})
                new_balance = wallet.get("balances", {}).get("USD", 0) if wallet else amount
                
                await telegram_bot.notify_deposit_completed(
                    user_id=user_id,
                    user_email=user_email,
                    amount=amount,
                    currency=deposit['pay_currency'],
                    order_id=order_id,
                    payment_id=payment_id,
                    new_balance=new_balance
                )
            except Exception as e:
                logger.warning(f"Failed to send completion Telegram notification: {e}")
                
        elif payment_status in PaymentStatus.FAILED_STATUSES:
            logger.warning(f"⚠️ Payment failed/expired: {order_id} - Status: {payment_status}")
            
            # Send failure notification to admin
            try:
                from services.telegram_bot import telegram_bot
                users_collection = db.get_collection("users")
                user = await users_collection.find_one({"id": deposit["user_id"]})
                user_email = user.get("email", "Unknown") if user else "Unknown"
                
                await telegram_bot.notify_deposit_failed(
                    user_id=deposit["user_id"],
                    user_email=user_email,
                    amount=deposit["amount"],
                    currency=deposit['pay_currency'],
                    order_id=order_id,
                    payment_id=payment_id,
                    reason=f"Payment status: {payment_status}"
                )
            except Exception as e:
                logger.warning(f"Failed to send failure Telegram notification: {e}")
        else:
            logger.info(f"ℹ️ Payment pending: {order_id} - Status: {payment_status}")
        
        return {
            "status": "success",
            "order_id": order_id,
            "payment_status": payment_status,
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing error in webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {str(e)}", exc_info=True)
        # Return 500 to trigger retry from webhook provider
        raise HTTPException(status_code=500, detail="Webhook processing failed")


# ============================================
# WEBHOOK TESTING ENDPOINT
# ============================================

@router.post("/webhook/test")
async def test_webhook_endpoint(request: Request):
    """
    Test endpoint to verify webhook is accessible and working.
    This endpoint accepts any JSON payload and returns diagnostic information.
    
    Usage:
    curl -X POST https://cryptovault-api.onrender.com/api/wallet/webhook/test \
         -H "Content-Type: application/json" \
         -d '{"test": "data"}'
    """
    try:
        body = await request.body()
        content_type = request.headers.get("content-type", "")
        
        # Try to parse JSON
        try:
            import json
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"error": "Invalid JSON"}
        
        return {
            "status": "success",
            "message": "Webhook endpoint is accessible and working",
            "received": {
                "content_type": content_type,
                "body_length": len(body),
                "payload": payload,
                "headers": dict(request.headers),
                "client_host": request.client.host if request.client else "unknown"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Test webhook error: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# ============================================
# WITHDRAWAL ENDPOINTS (placeholder)
# ============================================

@router.post("/withdraw")
async def create_withdrawal(
    data: WithdrawRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db),
    limiter = Depends(get_limiter)
):
    """
    Create a withdrawal request.
    Validates balance, creates withdrawal record, and initiates processing.
    """
    if not settings.feature_withdrawals_enabled:
        raise HTTPException(status_code=503, detail="Withdrawals are currently disabled")

    # Validate amount
    if data.amount < 10:
        raise HTTPException(status_code=400, detail="Minimum withdrawal is $10")
    
    if data.amount > 10000:
        raise HTTPException(status_code=400, detail="Maximum withdrawal is $10,000 per transaction")
    
    # Validate currency
    valid_currencies = ["USD", "BTC", "ETH", "USDT", "USDC"]
    if data.currency.upper() not in valid_currencies:
        raise HTTPException(status_code=400, detail=f"Invalid currency. Supported: {', '.join(valid_currencies)}")
    
    # Validate address format (basic validation)
    if not data.address or len(data.address.strip()) < 10:
        raise HTTPException(status_code=400, detail="Valid withdrawal address is required")
    
    # Check user's wallet balance
    wallets_collection = db.get_collection("wallets")
    wallet = await wallets_collection.find_one({"user_id": user_id})
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    current_balance = wallet.get("balances", {}).get(data.currency.upper(), 0)
    
    # Calculate withdrawal fee (1% with minimum $1)
    fee_percentage = 1.0  # 1%
    withdrawal_fee = max(data.amount * (fee_percentage / 100), 1.0)
    total_amount = data.amount + withdrawal_fee
    
    if current_balance < total_amount:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient balance. Required: ${total_amount:.2f} (including ${withdrawal_fee:.2f} fee), Available: ${current_balance:.2f}"
        )
    
    # Check if high-value withdrawal requiring multi-approval
    # Threshold: $5,000 requires at least 2 admin approvals
    MULTI_APPROVAL_THRESHOLD = 5000.0
    requires_multi_approval = data.amount >= MULTI_APPROVAL_THRESHOLD
    
    # Create withdrawal record
    withdrawals_collection = db.get_collection("withdrawals")
    withdrawal_id = str(uuid.uuid4())
    
    withdrawal_record = {
        "id": withdrawal_id,
        "user_id": user_id,
        "amount": data.amount,
        "currency": data.currency.upper(),
        "address": data.address.strip(),
        "status": "pending_approval" if requires_multi_approval else "pending",
        "fee": withdrawal_fee,
        "net_amount": data.amount,
        "total_amount": total_amount,
        "transaction_hash": None,
        "requires_multi_approval": requires_multi_approval,
        "required_approvals": 2 if requires_multi_approval else 0,
        "approval_count": 0,
        "approvals": [],  # [{admin_id, approved_at, ip_address}]
        "rejections": [],
        "created_at": datetime.utcnow(),
        "processed_at": None,
        "completed_at": None,
        "notes": f"High-value withdrawal (${data.amount:,.2f}) - requires 2 admin approvals" if requires_multi_approval else None,
    }
    
    await withdrawals_collection.insert_one(withdrawal_record)
    
    # Deduct from wallet balance (hold the funds)
    await wallets_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                f"balances.{data.currency.upper()}": current_balance - total_amount,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Create transaction record
    transactions_collection = db.get_collection("transactions")
    withdrawal_transaction = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "withdrawal",
        "amount": -data.amount,  # Negative for withdrawal
        "currency": data.currency.upper(),
        "status": "pending",
        "reference": withdrawal_id,
        "description": f"Withdrawal to {data.address[:12]}...",
        "created_at": datetime.utcnow()
    }
    await transactions_collection.insert_one(withdrawal_transaction)
    
    # Create fee transaction record
    fee_transaction = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "fee",
        "amount": -withdrawal_fee,  # Negative for fee
        "currency": data.currency.upper(),
        "status": "completed",
        "reference": withdrawal_id,
        "description": f"Withdrawal fee for {withdrawal_id[:8]}...",
        "created_at": datetime.utcnow()
    }
    await transactions_collection.insert_one(fee_transaction)

    await broadcast_transaction_event(user_id, withdrawal_transaction)
    await broadcast_transaction_event(user_id, fee_transaction)
    
    # Log audit
    await log_audit(
        db, user_id, "WITHDRAWAL_REQUESTED",
        resource=withdrawal_id,
        ip_address=request.client.host,
        details={
            "amount": data.amount,
            "currency": data.currency,
            "address": data.address[:12] + "...",  # Don't log full address
            "fee": withdrawal_fee
        }
    )
    
    # Send email notification (if email service is configured)
    try:
        users_collection = db.get_collection("users")
        user = await users_collection.find_one({"id": user_id})
        
        if user and user.get("email"):
            logger.info(f"Withdrawal notification email should be sent to {user['email']}")
    except Exception as e:
        logger.warning(f"Failed to send withdrawal notification email: {e}")
    
    # Send Telegram notification to admins
    try:
        from services.telegram_bot import telegram_bot
        users_collection = db.get_collection("users")
        user = await users_collection.find_one({"id": user_id})
        user_email = user.get("email", "Unknown") if user else "Unknown"

        if requires_multi_approval:
            await telegram_bot.notify_multi_approval_withdrawal(
                user_id=user_id,
                user_email=user_email,
                amount=data.amount,
                currency=data.currency.upper(),
                address=data.address,
                withdrawal_id=withdrawal_id,
                fee=withdrawal_fee,
                required_approvals=2,
            )
        else:
            await telegram_bot.notify_withdrawal_requested(
                user_id=user_id,
                user_email=user_email,
                amount=data.amount,
                currency=data.currency,
                address=data.address,
                withdrawal_id=withdrawal_id,
            )
    except Exception as e:
        logger.warning(f"Failed to send Telegram withdrawal notification: {e}")
    
    logger.info(f"✅ Withdrawal request created: {withdrawal_id} for ${data.amount}")
    
    return {
        "success": True,
        "withdrawalId": withdrawal_id,
        "amount": data.amount,
        "currency": data.currency.upper(),
        "address": data.address,
        "fee": withdrawal_fee,
        "totalAmount": total_amount,
        "status": "pending_approval" if requires_multi_approval else "pending",
        "requiresMultiApproval": requires_multi_approval,
        "requiredApprovals": 2 if requires_multi_approval else 0,
        "estimatedProcessingTime": "1-3 business days",
        "note": (
            f"High-value withdrawal (${data.amount:,.2f}) requires approval from 2 admins before processing."
            if requires_multi_approval
            else "Your withdrawal request has been received and will be processed within 1-3 business days."
        ),
    }


# ============================================
# MULTI-APPROVER WITHDRAWAL WORKFLOW
# ============================================

@router.post("/withdraw/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db),
):
    """
    Admin endpoint: Approve a high-value withdrawal.
    Requires at least 2 different admins to approve.
    """
    # Verify admin status
    users_collection = db.get_collection("users")
    admin_user = await users_collection.find_one({"id": user_id})
    if not admin_user or not admin_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    withdrawals_collection = db.get_collection("withdrawals")
    withdrawal = await withdrawals_collection.find_one({"id": withdrawal_id})

    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")

    if withdrawal["status"] not in ("pending_approval", "pending"):
        raise HTTPException(status_code=400, detail=f"Withdrawal is already {withdrawal['status']}")

    # Check if this admin already approved
    existing_approvals = withdrawal.get("approvals", [])
    if any(a["admin_id"] == user_id for a in existing_approvals):
        raise HTTPException(status_code=400, detail="You have already approved this withdrawal")

    # Add approval
    approval_record = {
        "admin_id": user_id,
        "admin_email": admin_user.get("email"),
        "approved_at": datetime.utcnow().isoformat(),
        "ip_address": request.client.host if request.client else None,
    }

    new_approval_count = len(existing_approvals) + 1
    required = withdrawal.get("required_approvals", 2)
    new_status = "pending" if new_approval_count >= required else "pending_approval"

    await withdrawals_collection.update_one(
        {"id": withdrawal_id},
        {
            "$push": {"approvals": approval_record},
            "$set": {
                "approval_count": new_approval_count,
                "status": new_status,
                "updated_at": datetime.utcnow(),
            },
        },
    )

    # Audit log
    await log_audit(
        db, user_id, "ADMIN_WITHDRAWAL_APPROVAL",
        resource=withdrawal_id,
        ip_address=request.client.host if request.client else None,
        details={
            "withdrawal_amount": withdrawal["amount"],
            "approval_count": new_approval_count,
            "required_approvals": required,
            "fully_approved": new_approval_count >= required,
        },
    )

    logger.info(
        "Withdrawal %s approved by admin %s (%d/%d approvals)",
        withdrawal_id, user_id, new_approval_count, required,
    )

    # Send Telegram notification about approval update
    try:
        from services.telegram_bot import telegram_bot
        await telegram_bot.notify_withdrawal_approval_update(
            withdrawal_id=withdrawal_id,
            admin_email=admin_user.get("email", "unknown"),
            action="approved",
            approval_count=new_approval_count,
            required_approvals=required,
            amount=withdrawal["amount"],
            currency=withdrawal["currency"],
        )
    except Exception as e:
        logger.warning(f"Failed to send Telegram approval notification: {e}")

    return {
        "success": True,
        "withdrawalId": withdrawal_id,
        "approvalCount": new_approval_count,
        "requiredApprovals": required,
        "fullyApproved": new_approval_count >= required,
        "newStatus": new_status,
    }


@router.post("/withdraw/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db),
):
    """Admin endpoint: Reject a withdrawal request and refund the user."""
    users_collection = db.get_collection("users")
    admin_user = await users_collection.find_one({"id": user_id})
    if not admin_user or not admin_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    withdrawals_collection = db.get_collection("withdrawals")
    withdrawal = await withdrawals_collection.find_one({"id": withdrawal_id})

    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")

    if withdrawal["status"] not in ("pending_approval", "pending"):
        raise HTTPException(status_code=400, detail=f"Withdrawal cannot be rejected (status: {withdrawal['status']})")

    # Refund user's wallet
    wallets_collection = db.get_collection("wallets")
    wallet = await wallets_collection.find_one({"user_id": withdrawal["user_id"]})
    if wallet:
        current_balance = wallet.get("balances", {}).get(withdrawal["currency"], 0)
        refund_amount = withdrawal.get("total_amount", withdrawal["amount"] + withdrawal.get("fee", 0))
        await wallets_collection.update_one(
            {"user_id": withdrawal["user_id"]},
            {"$set": {
                f"balances.{withdrawal['currency']}": current_balance + refund_amount,
                "updated_at": datetime.utcnow(),
            }},
        )

    await withdrawals_collection.update_one(
        {"id": withdrawal_id},
        {"$set": {
            "status": "rejected",
            "updated_at": datetime.utcnow(),
        },
        "$push": {"rejections": {
            "admin_id": user_id,
            "rejected_at": datetime.utcnow().isoformat(),
            "ip_address": request.client.host if request.client else None,
        }}},
    )

    await log_audit(
        db, user_id, "ADMIN_WITHDRAWAL_REJECTION",
        resource=withdrawal_id,
        ip_address=request.client.host if request.client else None,
        details={"withdrawal_amount": withdrawal["amount"]},
    )

    return {"success": True, "withdrawalId": withdrawal_id, "status": "rejected"}


@router.get("/withdrawals")
async def get_withdrawal_history(
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get user's withdrawal history."""
    withdrawals_collection = db.get_collection("withdrawals")
    
    withdrawals = await withdrawals_collection.find(
        {"user_id": user_id}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    total = await withdrawals_collection.count_documents({"user_id": user_id})
    
    return {
        "withdrawals": [
            {
                "id": w["id"],
                "amount": w["amount"],
                "currency": w["currency"],
                "address": w["address"],
                "status": w["status"],
                "fee": w["fee"],
                "totalAmount": w.get("total_amount", w["amount"] + w["fee"]),
                "transactionHash": w.get("transaction_hash"),
                "createdAt": w["created_at"].isoformat(),
                "processedAt": w.get("processed_at").isoformat() if w.get("processed_at") else None,
                "completedAt": w.get("completed_at").isoformat() if w.get("completed_at") else None
            }
            for w in withdrawals
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/withdraw/{withdrawal_id}")
async def get_withdrawal_status(
    withdrawal_id: str,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get status of a specific withdrawal."""
    withdrawals_collection = db.get_collection("withdrawals")

    withdrawal = await withdrawals_collection.find_one({
        "id": withdrawal_id,
        "user_id": user_id
    })

    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")

    return {
        "withdrawal": {
            "id": withdrawal["id"],
            "amount": withdrawal["amount"],
            "currency": withdrawal["currency"],
            "address": withdrawal["address"],
            "status": withdrawal["status"],
            "fee": withdrawal["fee"],
            "totalAmount": withdrawal.get("total_amount", withdrawal["amount"] + withdrawal["fee"]),
            "transactionHash": withdrawal.get("transaction_hash"),
            "createdAt": withdrawal["created_at"].isoformat(),
            "processedAt": withdrawal.get("processed_at").isoformat() if withdrawal.get("processed_at") else None,
            "completedAt": withdrawal.get("completed_at").isoformat() if withdrawal.get("completed_at") else None,
            "notes": withdrawal.get("notes")
        }
    }


# ============================================
# P2P TRANSFER ENDPOINTS
# ============================================

class TransferRequest(BaseModel):
    recipient_email: str
    amount: float
    currency: str = "USD"
    note: Optional[str] = None


@router.post("/transfer")
async def create_p2p_transfer(
    data: TransferRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db),
    limiter = Depends(get_limiter)
):
    """
    Create a peer-to-peer transfer to another user.
    Transfers are instant and free within the platform.
    """
    if not settings.feature_transfers_enabled:
        raise HTTPException(status_code=503, detail="Transfers are currently disabled")

    # Validate amount
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Transfer amount must be greater than 0")

    if data.amount < 1:
        raise HTTPException(status_code=400, detail="Minimum transfer amount is $1")

    if data.amount > 50000:
        raise HTTPException(status_code=400, detail="Maximum transfer amount is $50,000 per transaction")

    # Validate currency
    valid_currencies = ["USD", "BTC", "ETH", "USDT", "USDC"]
    if data.currency.upper() not in valid_currencies:
        raise HTTPException(status_code=400, detail=f"Invalid currency. Supported: {', '.join(valid_currencies)}")

    # Get sender's wallet
    users_collection = db.get_collection("users")
    wallets_collection = db.get_collection("wallets")
    transfers_collection = db.get_collection("transfers")
    transactions_collection = db.get_collection("transactions")

    sender = await users_collection.find_one({"id": user_id})
    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    # Check if sender is trying to send to themselves
    if sender["email"].lower() == data.recipient_email.lower():
        raise HTTPException(status_code=400, detail="Cannot transfer to yourself")

    # Find recipient by email
    recipient = await users_collection.find_one({"email": data.recipient_email.lower()})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found. User must have an account.")

    if not recipient.get("email_verified"):
        raise HTTPException(status_code=400, detail="Recipient's email is not verified. Ask them to verify their account first.")

    # Check sender's balance
    sender_wallet = await wallets_collection.find_one({"user_id": user_id})
    if not sender_wallet:
        raise HTTPException(status_code=404, detail="Sender wallet not found")

    sender_balance = sender_wallet.get("balances", {}).get(data.currency.upper(), 0)

    # P2P transfers are free (no fee)
    transfer_fee = 0.0
    total_amount = data.amount

    if sender_balance < total_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Required: {total_amount} {data.currency}, Available: {sender_balance} {data.currency}"
        )

    # Create transfer record
    transfer_id = str(uuid.uuid4())
    transfer_record = {
        "id": transfer_id,
        "sender_id": user_id,
        "sender_email": sender["email"],
        "sender_name": sender["name"],
        "recipient_id": recipient["id"],
        "recipient_email": recipient["email"],
        "recipient_name": recipient["name"],
        "amount": data.amount,
        "currency": data.currency.upper(),
        "fee": transfer_fee,
        "note": data.note,
        "status": "completed",  # P2P transfers are instant
        "created_at": datetime.utcnow(),
        "completed_at": datetime.utcnow()
    }

    await transfers_collection.insert_one(transfer_record)

    # Deduct from sender's wallet
    await wallets_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                f"balances.{data.currency.upper()}": sender_balance - total_amount,
                "updated_at": datetime.utcnow()
            }
        }
    )

    # Add to recipient's wallet (create if doesn't exist)
    recipient_wallet = await wallets_collection.find_one({"user_id": recipient["id"]})
    if recipient_wallet:
        recipient_balance = recipient_wallet.get("balances", {}).get(data.currency.upper(), 0)
        await wallets_collection.update_one(
            {"user_id": recipient["id"]},
            {
                "$set": {
                    f"balances.{data.currency.upper()}": recipient_balance + data.amount,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    else:
        # Create wallet for recipient
        await wallets_collection.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": recipient["id"],
            "balances": {data.currency.upper(): data.amount},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

    # Create transaction records for both users
    # Sender transaction
    sender_transaction = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "transfer_out",
        "amount": -data.amount,
        "currency": data.currency.upper(),
        "status": "completed",
        "reference": transfer_id,
        "description": f"Transfer to {recipient['name']} ({recipient['email']})",
        "created_at": datetime.utcnow()
    }
    await transactions_collection.insert_one(sender_transaction)

    # Recipient transaction
    recipient_transaction = {
        "id": str(uuid.uuid4()),
        "user_id": recipient["id"],
        "type": "transfer_in",
        "amount": data.amount,
        "currency": data.currency.upper(),
        "status": "completed",
        "reference": transfer_id,
        "description": f"Transfer from {sender['name']} ({sender['email']})",
        "created_at": datetime.utcnow()
    }
    await transactions_collection.insert_one(recipient_transaction)

    await broadcast_transaction_event(user_id, sender_transaction)
    await broadcast_transaction_event(recipient["id"], recipient_transaction)

    # Log audit events
    await log_audit(
        db, user_id, "P2P_TRANSFER_SENT",
        resource=transfer_id,
        ip_address=request.client.host,
        details={
            "recipient_email": recipient["email"],
            "amount": data.amount,
            "currency": data.currency
        }
    )

    await log_audit(
        db, recipient["id"], "P2P_TRANSFER_RECEIVED",
        resource=transfer_id,
        details={
            "sender_email": sender["email"],
            "amount": data.amount,
            "currency": data.currency
        }
    )

    logger.info(f"✅ P2P transfer completed: {transfer_id} - {data.amount} {data.currency} from {sender['email']} to {recipient['email']}")

    # Send transfer confirmation emails (non-blocking for business flow)
    try:
        amount_display = f"{data.amount:.8f}".rstrip('0').rstrip('.')
        await email_service.send_p2p_transfer_sent(
            to_email=sender["email"],
            sender_name=sender.get("name", "CryptoVault User"),
            recipient_name=recipient.get("name", "CryptoVault User"),
            recipient_email=recipient["email"],
            amount=amount_display,
            asset=data.currency.upper(),
            gas_fee="0",
            transaction_id=transfer_id,
            note=None,
        )
        await email_service.send_p2p_transfer_received(
            to_email=recipient["email"],
            recipient_name=recipient.get("name", "CryptoVault User"),
            sender_name=sender.get("name", "CryptoVault User"),
            sender_email=sender["email"],
            amount=amount_display,
            asset=data.currency.upper(),
            transaction_id=transfer_id,
            note=None,
        )
    except Exception as email_error:
        logger.warning(f"⚠️ Failed to send P2P transfer emails: {email_error}")

    return {
        "success": True,
        "transferId": transfer_id,
        "amount": data.amount,
        "currency": data.currency.upper(),
        "recipient": {
            "email": recipient["email"],
            "name": recipient["name"]
        },
        "fee": transfer_fee,
        "status": "completed",
        "message": f"Successfully transferred {data.amount} {data.currency} to {recipient['name']}"
    }


@router.get("/transfers")
async def get_transfer_history(
    skip: int = 0,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get user's P2P transfer history (both sent and received)."""
    transfers_collection = db.get_collection("transfers")

    # Find transfers where user is either sender or recipient
    transfers = await transfers_collection.find({
        "$or": [
            {"sender_id": user_id},
            {"recipient_id": user_id}
        ]
    }).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    total = await transfers_collection.count_documents({
        "$or": [
            {"sender_id": user_id},
            {"recipient_id": user_id}
        ]
    })

    # Format transfers with direction indicator
    formatted_transfers = []
    for transfer in transfers:
        is_sender = transfer["sender_id"] == user_id
        formatted_transfers.append({
            "id": transfer["id"],
            "amount": transfer["amount"],
            "currency": transfer["currency"],
            "direction": "sent" if is_sender else "received",
            "otherParty": {
                "email": transfer["recipient_email"] if is_sender else transfer["sender_email"],
                "name": transfer["recipient_name"] if is_sender else transfer["sender_name"]
            },
            "note": transfer.get("note"),
            "status": transfer["status"],
            "createdAt": transfer["created_at"].isoformat(),
            "completedAt": transfer.get("completed_at").isoformat() if transfer.get("completed_at") else None
        })

    return {
        "transfers": formatted_transfers,
        "total": total,
        "skip": skip,
        "limit": limit
    }
