"""
Database Query Optimization & Indexes
Provides guidance and utilities for optimal MongoDB performance
"""

import asyncio
import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryOptimization:
    """
    Database query optimization guide and utilities
    
    Best Practices for MongoDB:
    1. Always use indexed fields in query predicates
    2. Create compound indexes for common filter combinations
    3. Use projections to limit returned fields
    4. Use aggregation pipeline for complex queries
    5. Enable explain() on queries to analyze performance
    """
    
    # Compound indexes for hot queries
    RECOMMENDED_INDEXES = {
        "users": [
            # Auth lookups
            {"keys": [("email", 1)], "unique": True, "name": "email_unique"},
            # User discovery
            {"keys": [("created_at", -1)], "name": "created_at_desc"},
            # Email verification status
            {"keys": [("email_verified", 1), ("created_at", -1)], "name": "verified_recent"},
            # KYC status lookups
            {"keys": [("kyc_status", 1), ("created_at", -1)], "name": "kyc_status_recent"},
        ],
        
        "portfolio": [
            # Single portfolio per user (most common)
            {"keys": [("user_id", 1)], "unique": True, "name": "user_id_unique"},
            # Portfolio history
            {"keys": [("user_id", 1), ("updated_at", -1)], "name": "user_updates"},
        ],
        
        "transactions": [
            # User transaction history (most accessed)
            {"keys": [("user_id", 1), ("created_at", -1)], "name": "user_transactions"},
            # Transaction type filtering
            {"keys": [("user_id", 1), ("type", 1), ("created_at", -1)], "name": "user_type_date"},
            # Blockchain lookup
            {"keys": [("transaction_hash", 1)], "unique": True, "name": "tx_hash_unique"},
            # Status queries (for pending/failed)
            {"keys": [("status", 1), ("created_at", -1)], "name": "status_date"},
            # Fast status check for user's pending
            {"keys": [("user_id", 1), ("status", 1)], "name": "user_status"},
        ],
        
        "orders": [
            # User orders (most accessed)
            {"keys": [("user_id", 1), ("created_at", -1)], "name": "user_orders"},
            # Active order status
            {"keys": [("user_id", 1), ("status", 1)], "name": "user_order_status"},
            # Trading pair analysis
            {"keys": [("trading_pair", 1), ("created_at", -1)], "name": "pair_orders"},
            # Overall status (admin queries)
            {"keys": [("status", 1), ("created_at", -1)], "name": "status_orders"},
        ],
        
        "alerts": [
            # Active alerts by user
            {"keys": [("user_id", 1), ("is_active", 1)], "name": "user_alerts"},
            # Alerts for symbol
            {"keys": [("symbol", 1), ("is_active", 1)], "name": "symbol_alerts"},
            # Alert creation time
            {"keys": [("created_at", -1)], "name": "created_alerts"},
        ],
        
        "stakes": [
            # User stakes
            {"keys": [("user_id", 1), ("status", 1)], "name": "user_stakes"},
            # Recent stakes
            {"keys": [("user_id", 1), ("created_at", -1)], "name": "user_stakes_recent"},
            # Status tracking
            {"keys": [("status", 1), ("created_at", -1)], "name": "stake_status"},
        ],
        
        "referrals": [
            # User's referrals
            {"keys": [("referrer_id", 1), ("created_at", -1)], "name": "referrer_referrals"},
            # Referral earnings
            {"keys": [("referrer_id", 1), ("earned_amount", -1)], "name": "referrer_earnings"},
        ],
        
        "kyc_documents": [
            # User's KYC documents
            {"keys": [("user_id", 1), ("created_at", -1)], "name": "user_kyc_docs"},
            # Pending documents (for admin review)
            {"keys": [("status", 1), ("created_at", 1)], "name": "pending_kyc"},
        ],
        
        "audit_logs": [
            # User activity
            {"keys": [("user_id", 1), ("timestamp", -1)], "name": "user_activity"},
            # All logs chronologically
            {"keys": [("timestamp", -1)], "name": "latest_logs"},
            # Action filtering
            {"keys": [("action", 1), ("timestamp", -1)], "name": "action_logs"},
        ],
    }
    
    @staticmethod
    def get_query_optimization_tips() -> List[str]:
        """Get query optimization best practices"""
        return [
            "1. Use indexed fields in all WHERE clauses",
            "2. Create compound indexes for frequent filter combinations",
            "3. Use projections to only fetch needed fields",
            "4. Use aggregation pipeline for complex queries",
            "5. Use explain() to analyze slow queries",
            "6. Keep indexes on frequently updated fields minimal",
            "7. Drop unused indexes to speed up writes",
            "8. Use TTL indexes for auto-expiring data (sessions, OTPs)",
            "9. Run indexes during off-peak hours for large collections",
            "10. Monitor slow query log: db.setProfilingLevel(1)",
        ]
    
    @staticmethod
    def get_slow_query_threshold_ms() -> int:
        """Get slow query threshold for profiling"""
        return 100  # Log queries taking > 100ms


async def create_all_recommended_indexes(db):
    """
    Create all recommended indexes for optimal performance.
    Safe to run multiple times (existing indexes skipped).
    
    Args:
        db: Motor async database instance
    """
    logger.info("🔧 Creating recommended indexes for optimal performance...")
    
    total_created = 0
    
    for collection_name, indexes in QueryOptimization.RECOMMENDED_INDEXES.items():
        collection = db[collection_name]
        
        for index_config in indexes:
            try:
                keys = index_config["keys"]
                unique = index_config.get("unique", False)
                name = index_config.get("name")
                
                await collection.create_index(
                    keys,
                    unique=unique,
                    name=name,
                    background=True,  # Don't block other operations
                )
                
                total_created += 1
                logger.info(f"  ✅ {collection_name}.{name or 'index'}")
            
            except Exception as e:
                logger.warning(f"  ⚠️  {collection_name}: {str(e)}")
    
    logger.info(f"🎯 Created/verified {total_created} indexes")


async def analyze_collection_stats(db) -> dict:
    """
    Analyze database collection statistics.
    Shows document counts, sizes, and index usage.
    
    Args:
        db: Motor async database instance
    
    Returns:
        Dictionary with collection statistics
    """
    stats = {}
    
    for collection_name in await db.list_collection_names():
        try:
            collection = db[collection_name]
            count = await collection.count_documents({})
            
            # Get collection stats
            stats[collection_name] = {
                "documents": count,
                "indexed_fields": await _get_indexed_fields(collection),
            }
        
        except Exception as e:
            logger.warning(f"Could not get stats for {collection_name}: {str(e)}")
    
    return stats


async def _get_indexed_fields(collection) -> List[str]:
    """Get list of indexed fields for collection"""
    try:
        indexes = await collection.index_information()
        indexed_fields = []
        
        for index_name, index_info in indexes.items():
            if index_name != "_id_":  # Skip default _id index
                keys = [field[0] for field in index_info["key"]]
                indexed_fields.extend(keys)
        
        return list(set(indexed_fields))  # Remove duplicates
    
    except Exception:
        return []


def explain_query(query_dict: dict, projection: Optional[dict] = None) -> dict:
    """
    Generate query explanation for performance analysis.
    Shows execution plan and statistics.
    
    Args:
        query_dict: MongoDB query filter
        projection: Fields to return
    
    Returns:
        Explanation dictionary
    """
    return {
        "recommendation": "Use db.collection.find().explain('executionStats')",
        "query": query_dict,
        "projection": projection or {},
        "tips": [
            "Check 'winning' stage for execution plan",
            "Look at 'totalDocsExamined' vs 'nReturned'",
            "If examined > returned, you need better index",
            "Aim for 1:1 ratio of examined:returned documents",
        ],
    }


class IndexStatistics:
    """Track index usage and effectiveness"""
    
    def __init__(self):
        self.usage_count = {}
        self.execution_times = {}
    
    def record_query(self, index_name: str, execution_time_ms: float):
        """Record index usage"""
        if index_name not in self.usage_count:
            self.usage_count[index_name] = 0
            self.execution_times[index_name] = []
        
        self.usage_count[index_name] += 1
        self.execution_times[index_name].append(execution_time_ms)
    
    def get_statistics(self) -> dict:
        """Get index statistics"""
        stats = {}
        
        for index_name in self.usage_count:
            times = self.execution_times[index_name]
            avg_time = sum(times) / len(times) if times else 0
            
            stats[index_name] = {
                "usage_count": self.usage_count[index_name],
                "avg_execution_ms": avg_time,
                "min_execution_ms": min(times) if times else 0,
                "max_execution_ms": max(times) if times else 0,
            }
        
        return stats


# Global index statistics
index_stats = IndexStatistics()


# Slow query logging configuration
SLOW_QUERY_THRESHOLD_MS = 100
PROFILE_LEVEL = 1  # Log slow queries (0=off, 1=slow, 2=all)
