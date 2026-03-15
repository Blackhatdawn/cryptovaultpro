"""Push notification endpoints - FCM token management."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
import logging

from dependencies import get_current_user_id, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["push-notifications"])


class RegisterTokenRequest(BaseModel):
    token: str
    platform: Optional[str] = "web"  # web | android | ios


class TestPushRequest(BaseModel):
    title: Optional[str] = "CryptoVault Test"
    body: Optional[str] = "Push notifications are working!"


@router.post("/register-token")
async def register_fcm_token(
    data: RegisterTokenRequest,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Register or update a user's FCM device token for push notifications."""
    users_col = db.get_collection("users")

    await users_col.update_one(
        {"id": user_id},
        {
            "$set": {
                "fcm_token": data.token,
                "fcm_platform": data.platform,
                "fcm_token_updated_at": datetime.now(timezone.utc),
            }
        },
    )

    logger.info(f"FCM token registered for user {user_id} ({data.platform})")
    return {"message": "Push notification token registered", "platform": data.platform}


@router.delete("/unregister-token")
async def unregister_fcm_token(
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Remove FCM token (opt-out of push notifications)."""
    users_col = db.get_collection("users")

    await users_col.update_one(
        {"id": user_id},
        {"$unset": {"fcm_token": "", "fcm_platform": "", "fcm_token_updated_at": ""}},
    )

    return {"message": "Push notifications disabled"}


@router.post("/test")
async def test_push_notification(
    data: TestPushRequest,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Send a test push notification to the current user's registered device."""
    users_col = db.get_collection("users")
    user = await users_col.find_one({"id": user_id})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    fcm_token = user.get("fcm_token")
    if not fcm_token:
        raise HTTPException(
            status_code=400,
            detail="No push token registered. Enable notifications in your browser first.",
        )

    from fcm_service import fcm_service

    result = await fcm_service.send_notification(
        token=fcm_token,
        title=data.title,
        body=data.body,
        data={"type": "test", "timestamp": datetime.now(timezone.utc).isoformat()},
    )

    return {
        "message": "Test notification sent",
        "mock_mode": result.get("mock", False),
        "result": result,
    }


@router.get("/status")
async def push_status(
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Check if push notifications are enabled for the current user."""
    users_col = db.get_collection("users")
    user = await users_col.find_one({"id": user_id})

    has_token = bool(user.get("fcm_token")) if user else False
    from fcm_service import fcm_service

    return {
        "enabled": has_token,
        "platform": user.get("fcm_platform") if has_token else None,
        "mock_mode": fcm_service.mock_mode,
        "firebase_setup_required": fcm_service.mock_mode,
    }
