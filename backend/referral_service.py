"""
Referral System Service
Fixed bonus model: $10 credited to both referrer and referred user on signup.
Rewards are credited directly to wallet balance (USD).
"""
import random
import string
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from config import settings

logger = logging.getLogger(__name__)


class ReferralService:
    """Referral program management - Fixed bonus model"""

    SIGNUP_BONUS_REFERRER = 10.0   # $10 for the person who shared the code
    SIGNUP_BONUS_REFEREE  = 10.0   # $10 for the new user who signed up

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # Referral code helpers
    # ------------------------------------------------------------------

    def generate_referral_code(self, length: int = 8) -> str:
        chars = string.ascii_uppercase + string.digits
        chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
        return ''.join(random.choices(chars, k=length))

    async def get_or_create_referral_code(self, user_id: str) -> str:
        users_col = self.db.get_collection("users")
        user = await users_col.find_one({"id": user_id})
        if not user:
            raise ValueError("User not found")

        existing_code = user.get("referral_code")
        if existing_code:
            return existing_code

        for _ in range(10):
            code = self.generate_referral_code()
            if not await users_col.find_one({"referral_code": code}):
                await users_col.update_one(
                    {"id": user_id},
                    {"$set": {"referral_code": code, "referral_code_created_at": datetime.now(timezone.utc)}}
                )
                return code

        raise Exception("Failed to generate unique referral code")

    def normalize_referral_code(self, referral_code: str) -> str:
        return (referral_code or "").strip().upper()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate_referral_code(self, referee_id: str, referral_code: str) -> Dict[str, Any]:
        users_col = self.db.get_collection("users")
        referrals_col = self.db.get_collection("referrals")

        normalized_code = self.normalize_referral_code(referral_code)
        if not normalized_code:
            return {"success": False, "error": "Referral code is required"}

        referrer = await users_col.find_one({"referral_code": normalized_code})
        if not referrer:
            return {"success": False, "error": "Invalid referral code"}

        referrer_id = str(referrer.get("id") or referrer.get("_id"))

        if referrer_id == referee_id:
            return {"success": False, "error": "Cannot use your own referral code"}

        existing = await referrals_col.find_one({"referee_id": referee_id})
        if existing:
            return {"success": False, "error": "User already has a referrer"}

        return {
            "success": True,
            "referrer_id": referrer_id,
            "referrer_name": referrer.get("name", "A friend"),
            "referral_code": normalized_code,
        }

    # ------------------------------------------------------------------
    # Apply referral on signup  (core change: instant $10 both sides)
    # ------------------------------------------------------------------

    async def apply_referral_code(
        self,
        referee_id: str,
        referral_code: str,
        validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        users_col = self.db.get_collection("users")
        referrals_col = self.db.get_collection("referrals")
        wallets_col = self.db.get_collection("wallets")
        transactions_col = self.db.get_collection("transactions")

        if validation is None:
            validation = await self.validate_referral_code(referee_id, referral_code)
        if not validation.get("success"):
            return validation

        referrer_id = validation["referrer_id"]
        referral_code = validation["referral_code"]
        now = datetime.now(timezone.utc)

        # 1. Create referral record
        referral_doc = {
            "id": str(uuid.uuid4()),
            "referrer_id": referrer_id,
            "referee_id": referee_id,
            "referral_code": referral_code,
            "status": "qualified",
            "referrer_reward": self.SIGNUP_BONUS_REFERRER,
            "referee_reward": self.SIGNUP_BONUS_REFEREE,
            "created_at": now,
            "qualified_at": now,
        }
        await referrals_col.insert_one(referral_doc)

        # 2. Credit referee wallet ($10)
        await self._credit_wallet(wallets_col, referee_id, self.SIGNUP_BONUS_REFEREE)

        # 3. Credit referrer wallet ($10)
        await self._credit_wallet(wallets_col, referrer_id, self.SIGNUP_BONUS_REFERRER)

        # 4. Record transactions for audit trail
        for uid, amount, desc in [
            (referee_id, self.SIGNUP_BONUS_REFEREE, "Referral signup bonus (new user)"),
            (referrer_id, self.SIGNUP_BONUS_REFERRER, "Referral reward (friend joined)"),
        ]:
            await transactions_col.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "type": "referral_bonus",
                "amount": amount,
                "currency": "USD",
                "status": "completed",
                "description": desc,
                "metadata": {"referral_id": referral_doc["id"], "referral_code": referral_code},
                "created_at": now,
            })

        # 5. Update user stats
        await users_col.update_one(
            {"id": referrer_id},
            {
                "$inc": {"total_referrals": 1, "referral_earnings": self.SIGNUP_BONUS_REFERRER},
                "$push": {"referral_ids": referee_id},
            },
        )
        await users_col.update_one(
            {"id": referee_id},
            {"$set": {"referred_by": referrer_id, "referral_code_used": referral_code}},
        )

        # 6. Send in-app notifications (import lazily to avoid circular deps)
        try:
            from routers.notifications import create_notification
            await create_notification(
                self.db, referrer_id,
                title="Referral Reward!",
                message=f"Your friend just joined CryptoVault! ${self.SIGNUP_BONUS_REFERRER:.0f} has been added to your wallet.",
                notification_type="success",
                link="/referrals",
            )
            await create_notification(
                self.db, referee_id,
                title="Welcome Bonus!",
                message=f"You've received a ${self.SIGNUP_BONUS_REFEREE:.0f} signup bonus from your referral!",
                notification_type="success",
                link="/wallet",
            )
        except Exception as e:
            logger.warning(f"Failed to send referral notifications: {e}")

        # 7. Send push notification to referrer
        try:
            from fcm_service import fcm_service
            referrer = await users_col.find_one({"id": referrer_id})
            fcm_token = referrer.get("fcm_token") if referrer else None
            if fcm_token:
                await fcm_service.send_referral_notification(
                    token=fcm_token,
                    referee_name=validation["referrer_name"],
                    reward_amount=self.SIGNUP_BONUS_REFERRER,
                )
        except Exception:
            pass

        logger.info(f"Referral applied: {referee_id} referred by {referrer_id} | $10+$10 credited")

        return {
            "success": True,
            "referrer_name": validation["referrer_name"],
            "message": f"Referral bonus applied! ${self.SIGNUP_BONUS_REFEREE:.0f} has been added to your wallet.",
        }

    # ------------------------------------------------------------------
    # Wallet credit helper
    # ------------------------------------------------------------------

    async def _credit_wallet(self, wallets_col, user_id: str, amount: float):
        wallet = await wallets_col.find_one({"user_id": user_id})
        if wallet:
            current = wallet.get("balances", {}).get("USD", 0.0)
            await wallets_col.update_one(
                {"user_id": user_id},
                {"$set": {
                    "balances.USD": current + amount,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
        else:
            await wallets_col.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "balances": {"USD": amount},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })

    # ------------------------------------------------------------------
    # Stats & leaderboard
    # ------------------------------------------------------------------

    async def get_referral_stats(self, user_id: str) -> Dict[str, Any]:
        users_col = self.db.get_collection("users")
        referrals_col = self.db.get_collection("referrals")

        user = await users_col.find_one({"id": user_id})
        if not user:
            return {"error": "User not found"}

        referral_code = await self.get_or_create_referral_code(user_id)

        total_referrals = await referrals_col.count_documents({"referrer_id": user_id})
        qualified_referrals = await referrals_col.count_documents({"referrer_id": user_id, "status": "qualified"})
        pending_referrals = await referrals_col.count_documents({"referrer_id": user_id, "status": "pending"})

        total_earnings = user.get("referral_earnings", 0)

        recent_cursor = referrals_col.find({"referrer_id": user_id}).sort("created_at", -1).limit(10)
        recent_referrals = []
        async for ref in recent_cursor:
            referee = await users_col.find_one({"id": ref["referee_id"]})
            recent_referrals.append({
                "referee_name": (referee.get("name", "Anonymous")[:2] + "***") if referee else "Unknown",
                "status": ref["status"],
                "reward": ref.get("referrer_reward", 0),
                "created_at": ref["created_at"].isoformat() if ref.get("created_at") else None,
            })

        return {
            "referral_code": referral_code,
            "referral_link": f"{settings.app_url.rstrip('/')}/auth?ref={referral_code}",
            "total_referrals": total_referrals,
            "qualified_referrals": qualified_referrals,
            "pending_referrals": pending_referrals,
            "total_earnings": total_earnings,
            "bonus_per_referral": self.SIGNUP_BONUS_REFERRER,
            "recent_referrals": recent_referrals,
        }

    async def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        users_col = self.db.get_collection("users")
        cursor = users_col.find(
            {"referral_earnings": {"$gt": 0}},
            {"name": 1, "referral_earnings": 1, "total_referrals": 1, "_id": 0},
        ).sort("referral_earnings", -1).limit(limit)

        leaderboard = []
        rank = 1
        async for user in cursor:
            name = user.get("name", "Anonymous")
            masked = name[0] + "*" * (len(name) - 2) + name[-1] if len(name) > 2 else name
            leaderboard.append({
                "rank": rank,
                "name": masked,
                "referrals": user.get("total_referrals", 0),
                "earnings": user.get("referral_earnings", 0),
            })
            rank += 1

        return leaderboard
