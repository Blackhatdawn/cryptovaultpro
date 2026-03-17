"""
Referral System Service
Tiered bonus model with increasing rewards:
  - Bronze (0-4 referrals):  $10 per referral
  - Silver (5-9 referrals):  $15 per referral
  - Gold   (10-24 referrals): $20 per referral
  - Platinum (25+ referrals): $30 per referral

New users always receive a flat $10 signup bonus.
Rewards are credited directly to wallet balance (USD).
"""
import random
import string
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from config import settings

logger = logging.getLogger(__name__)


# Tier definitions: (min_referrals, tier_name, bonus_per_referral, badge_color)
REFERRAL_TIERS = [
    (0,  "Bronze",   10.0, "#CD7F32"),
    (5,  "Silver",   15.0, "#C0C0C0"),
    (10, "Gold",     20.0, "#FFD700"),
    (25, "Platinum", 30.0, "#E5E4E2"),
]

REFEREE_SIGNUP_BONUS = 10.0  # New user always gets $10


def get_tier(total_referrals: int) -> Dict[str, Any]:
    """Return the tier info for a given referral count."""
    tier = REFERRAL_TIERS[0]
    for min_refs, name, bonus, color in REFERRAL_TIERS:
        if total_referrals >= min_refs:
            tier = (min_refs, name, bonus, color)
    min_refs, name, bonus, color = tier

    # Calculate next tier
    next_tier = None
    for min_refs_next, name_next, bonus_next, color_next in REFERRAL_TIERS:
        if min_refs_next > total_referrals:
            next_tier = {
                "name": name_next,
                "referrals_needed": min_refs_next - total_referrals,
                "bonus": bonus_next,
                "color": color_next,
            }
            break

    return {
        "name": name,
        "bonus": bonus,
        "color": color,
        "min_referrals": min_refs,
        "next_tier": next_tier,
    }


class ReferralService:
    """Referral program management - Tiered bonus model"""

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
    # Apply referral on signup (tiered bonus for referrer, flat $10 for referee)
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

        # Determine referrer's current tier and bonus
        referrer = await users_col.find_one({"id": referrer_id})
        current_referrals = referrer.get("total_referrals", 0) if referrer else 0
        tier = get_tier(current_referrals)
        referrer_bonus = tier["bonus"]
        referee_bonus = REFEREE_SIGNUP_BONUS

        # 1. Create referral record
        referral_doc = {
            "id": str(uuid.uuid4()),
            "referrer_id": referrer_id,
            "referee_id": referee_id,
            "referral_code": referral_code,
            "status": "qualified",
            "referrer_reward": referrer_bonus,
            "referee_reward": referee_bonus,
            "referrer_tier": tier["name"],
            "created_at": now,
            "qualified_at": now,
        }
        await referrals_col.insert_one(referral_doc)

        # 2. Credit referee wallet (flat $10)
        await self._credit_wallet(wallets_col, referee_id, referee_bonus)

        # 3. Credit referrer wallet (tier-based bonus)
        await self._credit_wallet(wallets_col, referrer_id, referrer_bonus)

        # 4. Record transactions for audit trail
        for uid, amount, desc in [
            (referee_id, referee_bonus, "Referral signup bonus (new user)"),
            (referrer_id, referrer_bonus, f"Referral reward - {tier['name']} tier (friend joined)"),
        ]:
            await transactions_col.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "type": "referral_bonus",
                "amount": amount,
                "currency": "USD",
                "status": "completed",
                "description": desc,
                "metadata": {
                    "referral_id": referral_doc["id"],
                    "referral_code": referral_code,
                    "tier": tier["name"],
                },
                "created_at": now,
            })

        # 5. Update user stats
        new_total = current_referrals + 1
        new_tier = get_tier(new_total)

        await users_col.update_one(
            {"id": referrer_id},
            {
                "$inc": {"total_referrals": 1, "referral_earnings": referrer_bonus},
                "$push": {"referral_ids": referee_id},
                "$set": {"referral_tier": new_tier["name"]},
            },
        )
        await users_col.update_one(
            {"id": referee_id},
            {"$set": {"referred_by": referrer_id, "referral_code_used": referral_code}},
        )

        # 6. Send in-app notifications
        try:
            from routers.notifications import create_notification

            tier_upgrade_msg = ""
            if new_tier["name"] != tier["name"]:
                tier_upgrade_msg = f" You've been promoted to {new_tier['name']} tier!"

            await create_notification(
                self.db, referrer_id,
                title="Referral Reward!",
                message=f"Your friend joined! ${referrer_bonus:.0f} added to your wallet.{tier_upgrade_msg}",
                notification_type="success",
                link="/referrals",
            )
            await create_notification(
                self.db, referee_id,
                title="Welcome Bonus!",
                message=f"You've received a ${referee_bonus:.0f} signup bonus from your referral!",
                notification_type="success",
                link="/wallet",
            )
        except Exception as e:
            logger.warning(f"Failed to send referral notifications: {e}")

        # 7. Send push notification to referrer
        try:
            from fcm_service import fcm_service
            fcm_token = referrer.get("fcm_token") if referrer else None
            if fcm_token:
                await fcm_service.send_referral_notification(
                    token=fcm_token,
                    referee_name=validation.get("referrer_name", "A friend"),
                    reward_amount=referrer_bonus,
                )
        except Exception:
            pass

        logger.info(
            f"Referral applied: {referee_id} referred by {referrer_id} "
            f"| Referrer: ${referrer_bonus} ({tier['name']}) | Referee: ${referee_bonus}"
        )

        return {
            "success": True,
            "referrer_name": validation["referrer_name"],
            "message": f"Referral bonus applied! ${referee_bonus:.0f} has been added to your wallet.",
            "tier": tier["name"],
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
        tier = get_tier(total_referrals)

        recent_cursor = referrals_col.find({"referrer_id": user_id}).sort("created_at", -1).limit(10)
        recent_referrals = []
        async for ref in recent_cursor:
            referee = await users_col.find_one({"id": ref["referee_id"]})
            recent_referrals.append({
                "referee_name": (referee.get("name", "Anonymous")[:2] + "***") if referee else "Unknown",
                "status": ref["status"],
                "reward": ref.get("referrer_reward", 0),
                "tier_at_referral": ref.get("referrer_tier", "Bronze"),
                "created_at": ref["created_at"].isoformat() if ref.get("created_at") else None,
            })

        return {
            "referral_code": referral_code,
            "referral_link": f"{settings.app_url.rstrip('/')}/auth?ref={referral_code}",
            "total_referrals": total_referrals,
            "qualified_referrals": qualified_referrals,
            "pending_referrals": pending_referrals,
            "total_earnings": total_earnings,
            "tier": tier,
            "all_tiers": [
                {"name": name, "min_referrals": min_r, "bonus": bonus, "color": color}
                for min_r, name, bonus, color in REFERRAL_TIERS
            ],
            "recent_referrals": recent_referrals,
        }

    async def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        users_col = self.db.get_collection("users")
        cursor = users_col.find(
            {"referral_earnings": {"$gt": 0}},
            {"name": 1, "referral_earnings": 1, "total_referrals": 1, "referral_tier": 1, "_id": 0},
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
                "tier": user.get("referral_tier", "Bronze"),
            })
            rank += 1

        return leaderboard
