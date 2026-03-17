"""Referral endpoints for dashboard integrations."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user_id, get_db
from referral_service import ReferralService

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/summary")
async def get_referral_summary(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    service = ReferralService(db)
    stats = await service.get_referral_stats(user_id)
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])

    tier = stats["tier"]

    return {
        "referralCode": stats["referral_code"],
        "referralLink": stats["referral_link"],
        "totalReferrals": stats["total_referrals"],
        "activeReferrals": stats["qualified_referrals"],
        "pendingReferrals": stats["pending_referrals"],
        "totalEarned": float(stats["total_earnings"]),
        "tier": {
            "name": tier["name"],
            "bonus": tier["bonus"],
            "color": tier["color"],
            "nextTier": tier["next_tier"],
        },
        "allTiers": stats["all_tiers"],
        "recentReferrals": stats["recent_referrals"],
    }


@router.get("")
async def list_referrals(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    users = db.get_collection("users")
    referrals = db.get_collection("referrals")

    cursor = referrals.find({"referrer_id": user_id}).sort("created_at", -1).limit(100)
    items = []
    async for ref in cursor:
        referee = await users.find_one({"id": ref.get("referee_id")})
        email = referee.get("email") if referee else "hidden@example.com"
        masked_email = (email[:1] + "***@" + email.split("@")[-1]) if "@" in email else "hidden@example.com"
        items.append({
            "id": ref.get("id") or str(ref.get("_id")),
            "email": masked_email,
            "name": (referee.get("name", "")[:2] + "***") if referee else "Unknown",
            "status": ref.get("status", "pending"),
            "reward": round(float(ref.get("referrer_reward", 0.0)), 2),
            "tier": ref.get("referrer_tier", "Bronze"),
            "date": (ref.get("created_at") or datetime.now(timezone.utc)).isoformat(),
        })

    return {"referrals": items}


@router.get("/leaderboard")
async def get_leaderboard(db=Depends(get_db)):
    service = ReferralService(db)
    leaderboard = await service.get_leaderboard(limit=10)
    return {"leaderboard": leaderboard}
