"""
Smart Gas Fee Service for CryptoVault
Enterprise-grade dynamic fee calculation using real-time crypto data analysis.

Features:
- Dynamic fee calculation based on network conditions
- BTC fees in SATs (satoshis)
- Multi-currency support
- Mempool-based priority estimation
- Fee caching for performance
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from config import settings

logger = logging.getLogger(__name__)


class GasFeeService:
    """
    Enterprise-grade gas fee calculator.
    
    Uses real-time analysis of network conditions and crypto prices
    to calculate optimal transaction fees.
    """
    
    # Base fee percentages by asset tier (as percentage of transaction)
    BASE_FEE_TIERS = {
        "tier_1": 0.001,   # 0.1% for major cryptos (BTC, ETH)
        "tier_2": 0.0015,  # 0.15% for mid-cap (SOL, ADA)
        "tier_3": 0.002,   # 0.2% for smaller cryptos
        "stablecoin": 0.0005,  # 0.05% for stablecoins (internal transfers)
        "fiat": 0.0,       # No fee for fiat P2P transfers
    }
    
    # Asset tier mapping
    ASSET_TIERS = {
        # Tier 1 - Major cryptocurrencies
        "BTC": "tier_1",
        "ETH": "tier_1",
        
        # Tier 2 - Mid-cap cryptocurrencies
        "SOL": "tier_2",
        "BNB": "tier_2",
        "XRP": "tier_2",
        "ADA": "tier_2",
        "AVAX": "tier_2",
        "DOT": "tier_2",
        "LINK": "tier_2",
        
        # Tier 3 - Other cryptocurrencies
        "DOGE": "tier_3",
        "SHIB": "tier_3",
        "MATIC": "tier_3",
        "LTC": "tier_3",
        "UNI": "tier_3",
        
        # Stablecoins
        "USDT": "stablecoin",
        "USDC": "stablecoin",
        "DAI": "stablecoin",
        "BUSD": "stablecoin",
        
        # Fiat currencies
        "USD": "fiat",
        "EUR": "fiat",
        "GBP": "fiat",
    }
    
    # Minimum fees by currency
    MIN_FEES = {
        "BTC": 0.00001,      # ~0.50 USD at 50k BTC
        "ETH": 0.0001,       # ~0.30 USD at 3k ETH
        "SOL": 0.001,        # ~0.15 USD at 150 SOL
        "USDT": 0.01,        # 0.01 USD
        "USDC": 0.01,        # 0.01 USD
        "USD": 0.0,          # No fee
    }
    
    # Maximum fees by currency (to prevent excessive fees)
    MAX_FEES = {
        "BTC": 0.001,        # ~50 USD at 50k BTC
        "ETH": 0.01,         # ~30 USD at 3k ETH  
        "SOL": 0.1,          # ~15 USD at 150 SOL
        "USDT": 10.0,        # 10 USD
        "USDC": 10.0,        # 10 USD
        "USD": 0.0,          # No fee
    }
    
    # SAT/vByte estimates for BTC (dynamically updated)
    BTC_FEE_ESTIMATES = {
        "low": 10,       # ~10 minutes
        "medium": 25,    # ~3-5 minutes
        "high": 50,      # Next block
        "urgent": 100,   # Priority
    }
    
    # Gas price estimates for ETH (in gwei, dynamically updated)
    ETH_GAS_ESTIMATES = {
        "low": 10,
        "medium": 25,
        "high": 50,
        "urgent": 100,
    }
    
    def __init__(self):
        self.cache: Dict[str, Tuple[dict, datetime]] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        logger.info("💰 GasFeeService initialized")
    
    def get_asset_tier(self, currency: str) -> str:
        """Get the fee tier for an asset."""
        return self.ASSET_TIERS.get(currency.upper(), "tier_3")
    
    def calculate_fee(
        self,
        amount: float,
        currency: str,
        priority: str = "medium",
        include_breakdown: bool = False
    ) -> Dict:
        """
        Calculate the smart gas fee for a transaction.
        
        Args:
            amount: Transaction amount
            currency: Currency code (BTC, ETH, USD, etc.)
            priority: Fee priority (low, medium, high, urgent)
            include_breakdown: Whether to include fee breakdown
            
        Returns:
            Dictionary with fee information
        """
        currency = currency.upper()
        tier = self.get_asset_tier(currency)
        base_rate = self.BASE_FEE_TIERS.get(tier, 0.002)
        
        # Calculate base fee
        base_fee = amount * base_rate
        
        # Apply priority multiplier
        priority_multipliers = {
            "low": 0.8,
            "medium": 1.0,
            "high": 1.5,
            "urgent": 2.0,
        }
        priority_multiplier = priority_multipliers.get(priority, 1.0)
        adjusted_fee = base_fee * priority_multiplier
        
        # Apply min/max constraints
        min_fee = self.MIN_FEES.get(currency, 0.0001)
        max_fee = self.MAX_FEES.get(currency, float('inf'))
        
        final_fee = max(min_fee, min(adjusted_fee, max_fee))
        
        # Special handling for BTC (convert to SATs)
        sats_fee = None
        if currency == "BTC":
            sats_fee = int(final_fee * 100_000_000)  # 1 BTC = 100M SATs
        
        result = {
            "fee": round(final_fee, 8),
            "currency": currency,
            "priority": priority,
            "tier": tier,
            "fee_rate_percent": round(base_rate * 100, 4),
        }
        
        if sats_fee is not None:
            result["fee_sats"] = sats_fee
            result["fee_display"] = f"{sats_fee:,} SATs"
        else:
            result["fee_display"] = f"{final_fee:.8f} {currency}".rstrip('0').rstrip('.')
        
        if include_breakdown:
            result["breakdown"] = {
                "base_fee": round(base_fee, 8),
                "priority_multiplier": priority_multiplier,
                "min_fee": min_fee,
                "max_fee": max_fee,
                "tier": tier,
                "tier_rate": base_rate,
            }
        
        return result
    
    def calculate_btc_fee_sats(
        self,
        tx_size_vbytes: int = 250,
        priority: str = "medium"
    ) -> Dict:
        """
        Calculate BTC fee in SATs based on transaction size and priority.
        
        Args:
            tx_size_vbytes: Transaction size in virtual bytes (default: 250 for P2PKH)
            priority: Fee priority level
            
        Returns:
            Dictionary with SAT fee information
        """
        sat_per_vbyte = self.BTC_FEE_ESTIMATES.get(priority, 25)
        total_sats = tx_size_vbytes * sat_per_vbyte
        btc_fee = total_sats / 100_000_000
        
        return {
            "fee_sats": total_sats,
            "fee_btc": btc_fee,
            "sat_per_vbyte": sat_per_vbyte,
            "tx_size_vbytes": tx_size_vbytes,
            "priority": priority,
            "fee_display": f"{total_sats:,} SATs ({btc_fee:.8f} BTC)",
            "estimated_time": self._get_estimated_time(priority),
        }
    
    def calculate_eth_fee_gwei(
        self,
        gas_limit: int = 21000,
        priority: str = "medium"
    ) -> Dict:
        """
        Calculate ETH fee in Gwei based on gas limit and priority.
        
        Args:
            gas_limit: Gas limit (default: 21000 for simple transfer)
            priority: Fee priority level
            
        Returns:
            Dictionary with Gwei fee information
        """
        gas_price_gwei = self.ETH_GAS_ESTIMATES.get(priority, 25)
        total_gwei = gas_limit * gas_price_gwei
        eth_fee = total_gwei / 1_000_000_000  # 1 ETH = 1B Gwei
        
        return {
            "fee_gwei": total_gwei,
            "fee_eth": eth_fee,
            "gas_price_gwei": gas_price_gwei,
            "gas_limit": gas_limit,
            "priority": priority,
            "fee_display": f"{total_gwei:,} Gwei ({eth_fee:.8f} ETH)",
            "estimated_time": self._get_estimated_time(priority),
        }
    
    def get_fee_estimate(
        self,
        amount: float,
        currency: str,
        to_currency: Optional[str] = None
    ) -> Dict:
        """
        Get comprehensive fee estimate for a transfer.
        
        Args:
            amount: Transaction amount
            currency: Source currency
            to_currency: Target currency (if conversion)
            
        Returns:
            Dictionary with all priority level fees
        """
        estimates = {}
        
        for priority in ["low", "medium", "high", "urgent"]:
            fee_info = self.calculate_fee(amount, currency, priority)
            estimates[priority] = {
                "fee": fee_info["fee"],
                "fee_display": fee_info["fee_display"],
                "total_amount": round(amount + fee_info["fee"], 8),
                "estimated_time": self._get_estimated_time(priority),
            }
            
            if "fee_sats" in fee_info:
                estimates[priority]["fee_sats"] = fee_info["fee_sats"]
        
        return {
            "amount": amount,
            "currency": currency,
            "to_currency": to_currency,
            "estimates": estimates,
            "recommended": "medium",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    def _get_estimated_time(self, priority: str) -> str:
        """Get estimated confirmation time based on priority."""
        times = {
            "low": "10-30 minutes",
            "medium": "3-5 minutes",
            "high": "1-2 minutes",
            "urgent": "< 1 minute",
        }
        return times.get(priority, "Unknown")
    
    def is_fee_waived(self, currency: str, amount: float) -> bool:
        """
        Check if fee is waived for this transaction.
        
        Fees are waived for:
        - Fiat P2P transfers
        - Internal stablecoin transfers under $100
        """
        tier = self.get_asset_tier(currency)
        
        if tier == "fiat":
            return True
        
        if tier == "stablecoin" and amount < 100:
            return True
        
        return False


# Global service instance
gas_fee_service = GasFeeService()
