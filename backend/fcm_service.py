"""
Firebase Cloud Messaging (FCM) Service
Handles push notification delivery with automatic mock fallback.
Phase 3: Circuit breaker pattern for Firebase fault tolerance
"""
import json
import os
import logging
from typing import Optional, Dict, Any

from config import settings

# Phase 3 Fault Tolerance
from circuit_breaker import with_circuit_breaker, BREAKER_FIREBASE

logger = logging.getLogger(__name__)


class FCMService:
    """Firebase Cloud Messaging service with graceful fallback."""

    def __init__(self):
        self.mock_mode = True
        self.app = None
        self._initialize()

    def _initialize(self):
        """Try to initialize Firebase Admin SDK."""
        try:
            import firebase_admin
            from firebase_admin import credentials

            # Option 1: JSON string from environment variable
            creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
            if creds_json:
                cred_dict = json.loads(creds_json)
                cred = credentials.Certificate(cred_dict)
                self.app = firebase_admin.initialize_app(cred)
                self.mock_mode = False
                logger.info("FCM initialized from FIREBASE_CREDENTIALS_JSON")
                return

            # Option 2: JSON file path from env or settings
            creds_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
            if not creds_path:
                try:
                    from config import settings
                    creds_path = getattr(settings, 'firebase_credentials_path', None)
                except Exception:
                    pass

            if creds_path and os.path.exists(creds_path):
                cred = credentials.Certificate(creds_path)
                self.app = firebase_admin.initialize_app(cred)
                self.mock_mode = False
                logger.info(f"FCM initialized from {creds_path}")
                return

            # Option 3: Try default path
            default_path = "/app/backend/firebase-credentials.json"
            if os.path.exists(default_path):
                cred = credentials.Certificate(default_path)
                self.app = firebase_admin.initialize_app(cred)
                self.mock_mode = False
                logger.info(f"FCM initialized from default path {default_path}")
                return

            logger.info("FCM running in MOCK mode (no Firebase credentials found)")

        except Exception as e:
            logger.warning(f"FCM initialization failed, using mock mode: {e}")
            self.mock_mode = True

    @with_circuit_breaker(breaker=BREAKER_FIREBASE, fallback_func=lambda *args, **kwargs: {"mock": False, "status": "error", "error": "Firebase unavailable"})
    async def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a push notification to a single device with circuit breaker protection (Phase 3)."""
        if self.mock_mode:
            logger.info(f"[MOCK FCM] -> {title}: {body} (token: {token[:20]}...)")
            return {"mock": True, "status": "sent", "title": title}

        try:
            from firebase_admin import messaging

            notification = messaging.Notification(
                title=title,
                body=body,
                image=image,
            )

            message = messaging.Message(
                notification=notification,
                token=token,
                data=data or {},
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        icon="/logo.svg",
                        badge="/logo.svg",
                    ),
                ),
            )

            response = messaging.send(message)
            logger.info(f"FCM sent: {response}")
            return {"mock": False, "status": "sent", "message_id": response}

        except Exception as e:
            logger.error(f"FCM send failed: {e}")
            return {"mock": False, "status": "error", "error": str(e)}

    @with_circuit_breaker(breaker=BREAKER_FIREBASE, fallback_func=lambda *args, **kwargs: {"mock": False, "status": "error", "error": "Firebase unavailable"})
    async def send_to_multiple(
        self,
        tokens: list,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send notification to multiple devices with circuit breaker protection (Phase 3)."""
        if self.mock_mode:
            logger.info(f"[MOCK FCM] -> {title} to {len(tokens)} devices")
            return {"mock": True, "status": "sent", "count": len(tokens)}

        try:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                tokens=tokens,
                data=data or {},
            )

            response = messaging.send_each_for_multicast(message)
            logger.info(f"FCM multicast: {response.success_count} sent, {response.failure_count} failed")
            return {
                "mock": False,
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }

        except Exception as e:
            logger.error(f"FCM multicast failed: {e}")
            return {"mock": False, "status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Convenience methods for common notification types
    # ------------------------------------------------------------------

    async def send_referral_notification(self, token: str, referee_name: str, reward_amount: float):
        return await self.send_notification(
            token=token,
            title="Referral Reward!",
            body=f"Your friend just joined CryptoVault! ${reward_amount:.0f} has been added to your wallet.",
            data={"type": "referral_reward", "amount": str(reward_amount)},
        )

    async def send_price_alert(self, token: str, symbol: str, price: float, direction: str):
        arrow = "above" if direction == "above" else "below"
        return await self.send_notification(
            token=token,
            title=f"Price Alert: {symbol}",
            body=f"{symbol} is now {arrow} ${price:,.2f}",
            data={"type": "price_alert", "symbol": symbol, "price": str(price)},
        )

    async def send_order_notification(self, token: str, order_type: str, symbol: str, status: str):
        return await self.send_notification(
            token=token,
            title=f"Order {status.title()}",
            body=f"Your {order_type} order for {symbol} has been {status}.",
            data={"type": "order_confirmation", "symbol": symbol, "status": status},
        )

    async def send_deposit_notification(self, token: str, amount: float, currency: str):
        return await self.send_notification(
            token=token,
            title="Deposit Confirmed",
            body=f"${amount:,.2f} {currency} has been credited to your wallet.",
            data={"type": "deposit_confirmation", "amount": str(amount), "currency": currency},
        )


# Global singleton
fcm_service = FCMService()
