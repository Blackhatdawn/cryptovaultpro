"""
Enterprise Password Reset Service
Advanced security features for password management
"""

import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


class PasswordResetService:
    """Enterprise-grade password reset service"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.reset_attempts_collection = db.password_reset_attempts
        self.reset_tokens_collection = db.password_reset_tokens
        self.password_history_collection = db.password_history
        
    async def check_rate_limit(self, email: str, ip_address: str) -> Dict[str, Any]:
        """
        Check if password reset is rate limited
        
        Returns:
            {
                "allowed": bool,
                "attempts_remaining": int,
                "retry_after_seconds": int
            }
        """
        # Check email-based rate limit (3 attempts per hour)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        email_attempts = await self.reset_attempts_collection.count_documents({
            "email": email.lower(),
            "created_at": {"$gte": one_hour_ago}
        })
        
        if email_attempts >= 3:
            # Calculate retry time
            oldest_attempt = await self.reset_attempts_collection.find_one(
                {"email": email.lower(), "created_at": {"$gte": one_hour_ago}},
                sort=[("created_at", 1)]
            )
            
            if oldest_attempt:
                retry_after = (oldest_attempt["created_at"] + timedelta(hours=1) - datetime.now(timezone.utc)).total_seconds()
                return {
                    "allowed": False,
                    "attempts_remaining": 0,
                    "retry_after_seconds": max(int(retry_after), 60)
                }
        
        # Check IP-based rate limit (5 attempts per hour)
        ip_attempts = await self.reset_attempts_collection.count_documents({
            "ip_address": ip_address,
            "created_at": {"$gte": one_hour_ago}
        })
        
        if ip_attempts >= 5:
            return {
                "allowed": False,
                "attempts_remaining": 0,
                "retry_after_seconds": 3600
            }
        
        return {
            "allowed": True,
            "attempts_remaining": 3 - email_attempts,
            "retry_after_seconds": 0
        }
    
    async def generate_reset_token(
        self, 
        user_id: str, 
        email: str,
        ip_address: str,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Generate secure password reset token
        
        Returns:
            token: str - 256-bit URL-safe token
        """
        # Generate cryptographically secure token
        token = secrets.token_urlsafe(32)  # 256 bits of entropy
        
        # Hash token for storage (never store plain tokens)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Store token with metadata
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)  # 15 minute expiration
        
        await self.reset_tokens_collection.insert_one({
            "token_hash": token_hash,
            "user_id": user_id,
            "email": email.lower(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "used": False,
            "used_at": None
        })
        
        # Log attempt
        await self.reset_attempts_collection.insert_one({
            "email": email.lower(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(timezone.utc),
            "success": True
        })
        
        logger.info(f"Password reset token generated for user {user_id} from IP {ip_address}")
        
        return token
    
    async def validate_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate password reset token
        
        Returns:
            Token data if valid, None if invalid
        """
        # Hash provided token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Find token
        token_doc = await self.reset_tokens_collection.find_one({
            "token_hash": token_hash,
            "used": False
        })
        
        if not token_doc:
            logger.warning(f"Invalid or already used reset token attempted")
            return None
        
        # Check expiration
        if datetime.now(timezone.utc) > token_doc["expires_at"]:
            logger.warning(f"Expired reset token attempted for user {token_doc['user_id']}")
            return None
        
        return token_doc
    
    async def mark_token_used(self, token: str):
        """Mark token as used"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        await self.reset_tokens_collection.update_one(
            {"token_hash": token_hash},
            {
                "$set": {
                    "used": True,
                    "used_at": datetime.now(timezone.utc)
                }
            }
        )
    
    async def check_password_history(
        self, 
        user_id: str, 
        new_password_hash: str,
        history_limit: int = 3
    ) -> bool:
        """
        Check if password was used recently
        
        Returns:
            True if password is unique (allowed), False if already used
        """
        # Get recent password hashes
        recent_passwords = await self.password_history_collection.find(
            {"user_id": user_id},
            sort=[("created_at", -1)],
            limit=history_limit
        ).to_list(history_limit)
        
        # Check if new password matches any recent password
        for old_password in recent_passwords:
            if old_password["password_hash"] == new_password_hash:
                logger.warning(f"User {user_id} attempted to reuse recent password")
                return False
        
        return True
    
    async def add_password_to_history(self, user_id: str, password_hash: str):
        """Add password to history"""
        await self.password_history_collection.insert_one({
            "user_id": user_id,
            "password_hash": password_hash,
            "created_at": datetime.now(timezone.utc)
        })
        
        # Keep only last 5 passwords
        all_passwords = await self.password_history_collection.find(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        ).to_list(10)
        
        if len(all_passwords) > 5:
            # Delete oldest passwords
            old_ids = [p["_id"] for p in all_passwords[5:]]
            await self.password_history_collection.delete_many({
                "_id": {"$in": old_ids}
            })
    
    async def check_account_lockout(self, user_id: str) -> Dict[str, Any]:
        """
        Check if account is locked due to failed reset attempts
        
        Returns:
            {
                "locked": bool,
                "unlock_at": datetime,
                "reason": str
            }
        """
        # Check for failed attempts in last 24 hours
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        
        failed_attempts = await self.reset_attempts_collection.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": twenty_four_hours_ago},
            "success": False
        })
        
        if failed_attempts >= 5:
            oldest_attempt = await self.reset_attempts_collection.find_one(
                {"user_id": user_id, "created_at": {"$gte": twenty_four_hours_ago}},
                sort=[("created_at", 1)]
            )
            
            unlock_at = oldest_attempt["created_at"] + timedelta(hours=24)
            
            return {
                "locked": True,
                "unlock_at": unlock_at,
                "reason": "Too many failed password reset attempts"
            }
        
        return {"locked": False}
    
    async def log_failed_attempt(
        self, 
        email: str, 
        user_id: Optional[str],
        ip_address: str,
        reason: str
    ):
        """Log failed password reset attempt"""
        await self.reset_attempts_collection.insert_one({
            "email": email.lower(),
            "user_id": user_id,
            "ip_address": ip_address,
            "created_at": datetime.now(timezone.utc),
            "success": False,
            "failure_reason": reason
        })
        
        logger.warning(f"Failed password reset attempt: {email} from {ip_address} - {reason}")
    
    async def cleanup_expired_tokens(self):
        """Cleanup expired tokens (run periodically)"""
        result = await self.reset_tokens_collection.delete_many({
            "expires_at": {"$lt": datetime.now(timezone.utc)}
        })
        
        if result.deleted_count > 0:
            logger.info(f"Cleaned up {result.deleted_count} expired password reset tokens")
    
    async def get_reset_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get password reset statistics for user"""
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        
        total_attempts = await self.reset_attempts_collection.count_documents({
            "user_id": user_id
        })
        
        recent_attempts = await self.reset_attempts_collection.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": twenty_four_hours_ago}
        })
        
        successful_resets = await self.reset_tokens_collection.count_documents({
            "user_id": user_id,
            "used": True
        })
        
        return {
            "total_attempts": total_attempts,
            "recent_attempts_24h": recent_attempts,
            "successful_resets": successful_resets
        }
