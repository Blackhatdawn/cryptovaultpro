"""
Enterprise-Grade Startup and Initialization Module

Handles:
- Environment validation
- Dependency checks (MongoDB, Redis, external services)
- Graceful fallback mechanisms
- Structured initialization logging
"""

import logging
import asyncio
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StartupHealthCheck:
    """Comprehensive startup health check system"""
    
    def __init__(self):
        self.checks: Dict[str, Dict] = {}
        self.critical_failures: List[str] = []
        self.warnings: List[str] = []
        self.info_messages: List[str] = []
    
    def add_check(self, name: str, status: str, message: str = "", is_critical: bool = False):
        """
        Add a startup check result
        
        Args:
            name: Check name
            status: 'PASS', 'WARN', 'FAIL'
            message: Status message
            is_critical: If True, failure blocks startup
        """
        self.checks[name] = {
            "status": status,
            "message": message,
            "critical": is_critical,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if status == "FAIL" and is_critical:
            self.critical_failures.append(f"{name}: {message}")
        elif status == "WARN":
            self.warnings.append(f"{name}: {message}")
        elif status == "PASS":
            self.info_messages.append(f"✅ {name}")
    
    def get_summary(self) -> Tuple[bool, Dict]:
        """
        Get startup summary
        
        Returns:
            (can_start: bool, summary_dict)
        """
        can_start = len(self.critical_failures) == 0
        
        return can_start, {
            "can_start": can_start,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": self.checks,
            "critical_failures": self.critical_failures,
            "warnings": self.warnings,
            "passed": len([c for c in self.checks.values() if c["status"] == "PASS"]),
            "failed": len([c for c in self.checks.values() if c["status"] == "FAIL"]),
            "warnings_count": len(self.warnings)
        }
    
    def log_summary(self):
        """Log startup summary with ASCII formatting"""
        can_start, summary = self.get_summary()
        
        print("\n" + "=" * 80)
        print("🔍 STARTUP HEALTH CHECK SUMMARY")
        print("=" * 80)
        
        # Passed checks
        if summary["passed"] > 0:
            print(f"\n✅ PASSED: {summary['passed']} checks")
            for name, check in self.checks.items():
                if check["status"] == "PASS":
                    print(f"   • {name}")
        
        # Warnings
        if summary["warnings_count"] > 0:
            print(f"\n⚠️  WARNINGS: {summary['warnings_count']} notices")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        # Critical failures
        if self.critical_failures:
            print(f"\n❌ CRITICAL FAILURES: {len(self.critical_failures)}")
            for failure in self.critical_failures:
                print(f"   • {failure}")
        
        # Final status
        print("\n" + "-" * 80)
        if can_start:
            print(f"✅ STATUS: READY TO START (with {summary['warnings_count']} warnings)")
        else:
            print(f"❌ STATUS: CANNOT START ({len(self.critical_failures)} critical issues)")
        print("=" * 80 + "\n")


async def check_mongodb_connection(health_check: StartupHealthCheck):
    """Check MongoDB connectivity"""
    try:
        from dependencies import get_db_connection
        
        db_conn = get_db_connection()
        if db_conn and await db_conn.health_check():
            health_check.add_check(
                "MongoDB Connection",
                "PASS",
                "Successfully connected to MongoDB",
                is_critical=True
            )
        else:
            health_check.add_check(
                "MongoDB Connection",
                "FAIL",
                "Database connection check failed",
                is_critical=True
            )
    except Exception as e:
        health_check.add_check(
            "MongoDB Connection",
            "FAIL",
            str(e),
            is_critical=True
        )


async def check_redis_connection(health_check: StartupHealthCheck):
    """Check Redis connectivity"""
    try:
        from config import settings
        
        if not settings.is_redis_available():
            health_check.add_check(
                "Redis Connection",
                "WARN",
                "Redis not configured - using in-memory fallback",
                is_critical=False
            )
            return
        
        from redis_cache import redis_cache
        
        # Test Redis with timeout
        try:
            await asyncio.wait_for(redis_cache._ensure_client(), timeout=5.0)
            health_check.add_check(
                "Redis Connection",
                "PASS",
                "Successfully connected to Redis",
                is_critical=False
            )
        except asyncio.TimeoutError:
            health_check.add_check(
                "Redis Connection",
                "WARN",
                "Redis connection timeout - using in-memory fallback",
                is_critical=False
            )
    except Exception as e:
        health_check.add_check(
            "Redis Connection",
            "WARN",
            f"Redis unavailable - {str(e)} - using in-memory fallback",
            is_critical=False
        )


async def check_external_services(health_check: StartupHealthCheck):
    """Check external service availability"""
    from config import settings
    
    # Check price stream service
    try:
        from services.price_stream_service import price_stream_service
        
        if await asyncio.wait_for(price_stream_service.ping(), timeout=3.0):
            health_check.add_check(
                "Price Stream Service",
                "PASS",
                "Price stream service responsive",
                is_critical=False
            )
        else:
            health_check.add_check(
                "Price Stream Service",
                "WARN",
                "Price stream service not responsive - caching will be used",
                is_critical=False
            )
    except Exception as e:
        health_check.add_check(
            "Price Stream Service",
            "WARN",
            f"Price stream unavailable: {str(e)}",
            is_critical=False
        )
    
    # Check Telegram bot
    if settings.telegram_enabled:
        try:
            from services.telegram_bot import telegram_bot
            
            status = await telegram_bot.get_health_status()
            if status.get("enabled") and status.get("api_reachable"):
                health_check.add_check(
                    "Telegram Bot",
                    "PASS",
                    f"Bot @{status.get('bot_username', 'unknown')} operational",
                    is_critical=False
                )
            else:
                health_check.add_check(
                    "Telegram Bot",
                    "WARN",
                    "Telegram bot not fully operational - notifications disabled",
                    is_critical=False
                )
        except Exception as e:
            health_check.add_check(
                "Telegram Bot",
                "WARN",
                f"Telegram bot error: {str(e)}",
                is_critical=False
            )


async def validate_configuration(health_check: StartupHealthCheck):
    """Validate critical configuration"""
    from config import settings, validate_startup_environment
    
    try:
        result = validate_startup_environment()
        if not result.get("status") == "valid":
            for error in result.get("errors", []):
                health_check.add_check(
                    "Configuration Validation",
                    "FAIL",
                    error,
                    is_critical=True
                )
            return
        
        health_check.add_check(
            "Configuration Validation",
            "PASS",
            "All critical environment variables configured",
            is_critical=True
        )
    except ValueError as e:
        health_check.add_check(
            "Configuration Validation",
            "FAIL",
            str(e),
            is_critical=True
        )
    except Exception as e:
        health_check.add_check(
            "Configuration Validation",
            "WARN",
            f"Configuration check error: {str(e)}",
            is_critical=False
        )


async def run_startup_checks() -> Tuple[bool, StartupHealthCheck]:
    """
    Run all startup checks in parallel
    
    Returns:
        (can_start: bool, health_check: StartupHealthCheck)
    """
    health_check = StartupHealthCheck()
    
    logger.info("🚀 Running startup health checks...")
    
    # Run checks in parallel with timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(
                validate_configuration(health_check),
                check_mongodb_connection(health_check),
                check_redis_connection(health_check),
                check_external_services(health_check),
                return_exceptions=True
            ),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        health_check.add_check(
            "Startup Checks Timeout",
            "FAIL",
            "Startup checks exceeded 30-second timeout",
            is_critical=True
        )
    
    can_start, _ = health_check.get_summary()
    health_check.log_summary()
    
    return can_start, health_check
