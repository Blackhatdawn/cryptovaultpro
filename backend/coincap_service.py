"""
Market data service (CoinGecko-backed).

Note: kept module/class name for backward compatibility with existing imports.
Phase 2: Request retry logic for external API reliability
"""
import httpx
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
import random

from config import settings
from redis_cache import redis_cache

# Phase 2 Performance Optimization
from request_retry import with_retry, RETRY_API, RetryConfig
from performance_monitoring import performance_metrics, RequestTimer

# Phase 3 Fault Tolerance
from circuit_breaker import with_circuit_breaker, BREAKER_COINCAP

logger = logging.getLogger(__name__)


class CoinCapService:
    """Backward-compatible market data service powered by CoinGecko."""

    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.use_mock = settings.use_mock_prices
        self.timeout = 15
        self._api_error_logged = False

        self.tracked_coins = [
            "bitcoin", "ethereum", "binancecoin", "cardano", "solana",
            "ripple", "polkadot", "dogecoin", "avalanche-2", "matic-network",
            "chainlink", "litecoin", "uniswap", "stellar", "tron",
            "cosmos", "near", "bitcoin-cash", "algorand", "vechain"
        ]

    async def get_prices(self, coin_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        cached_prices = await redis_cache.get_cached_prices()
        if cached_prices:
            return cached_prices

        ids = [self._normalize_coin_id(coin_id) for coin_id in (coin_ids or self.tracked_coins)]
        if self.use_mock:
            prices = self._get_mock_prices(ids)
            await redis_cache.cache_prices(prices)
            return prices

        try:
            prices = await self._fetch_real_prices(ids)
            await redis_cache.cache_prices(prices)
            self._api_error_logged = False
            return prices
        except Exception as e:
            if not self._api_error_logged:
                logger.error("❌ CoinGecko API error: %s. Falling back to mock data.", str(e))
                self._api_error_logged = True
            prices = self._get_mock_prices(ids)
            await redis_cache.cache_prices(prices)
            return prices

    @with_circuit_breaker(breaker=BREAKER_COINCAP, fallback_func=lambda *args, **kwargs: [])
    @with_retry(config=RETRY_API)
    async def _fetch_real_prices(self, coin_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch real prices from CoinGecko with circuit breaker (Phase 3) and retry logic (Phase 2).
        
        Circuit Breaker States:
        - CLOSED: Normal operation, requests go through
        - OPEN: CoinGecko failing, returns empty list fallback
        - HALF_OPEN: Automatic recovery test after 60s timeout
        """
        ids = [self._normalize_coin_id(coin_id) for coin_id in (coin_ids or self.tracked_coins)]
        async with RequestTimer("fetch-real-prices-circuit-protected"):
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": ",".join(ids),
                        "order": "market_cap_desc",
                        "per_page": min(max(len(ids), 20), 250),
                        "page": 1,
                        "sparkline": "false",
                        "price_change_percentage": "24h",
                    },
                )
                response.raise_for_status()
                assets = response.json()

        logger.info("✅ Fetched %s prices from CoinGecko", len(assets))
        results: List[Dict[str, Any]] = []
        for rank, asset in enumerate(assets, start=1):
            results.append({
                "id": asset.get("id"),
                "symbol": (asset.get("symbol") or "").upper(),
                "name": asset.get("name"),
                "price": float(asset.get("current_price") or 0),
                "market_cap": float(asset.get("market_cap") or 0),
                "volume_24h": float(asset.get("total_volume") or 0),
                "change_24h": round(float(asset.get("price_change_percentage_24h") or 0), 2),
                "rank": int(asset.get("market_cap_rank") or rank),
                "supply": float(asset.get("circulating_supply") or 0),
                "max_supply": float(asset.get("max_supply") or 0) if asset.get("max_supply") else None,
                "image": asset.get("image") or "",
                "last_updated": asset.get("last_updated") or datetime.now(timezone.utc).isoformat(),
                "source": "coingecko",
            })
        return results

    def _normalize_coin_id(self, coin_id: str) -> str:
        mapping = {
            "binance-coin": "binancecoin",
            "polygon": "matic-network",
            "xrp": "ripple",
            "near-protocol": "near",
            "avax": "avalanche-2",
        }
        return mapping.get((coin_id or "").lower(), (coin_id or "").lower())

    def _get_mock_prices(self, coin_ids: List[str]) -> List[Dict[str, Any]]:
        mock_data = {
            "bitcoin": {"name": "Bitcoin", "symbol": "BTC", "base_price": 68000, "rank": 1},
            "ethereum": {"name": "Ethereum", "symbol": "ETH", "base_price": 3500, "rank": 2},
            "binancecoin": {"name": "BNB", "symbol": "BNB", "base_price": 600, "rank": 3},
            "solana": {"name": "Solana", "symbol": "SOL", "base_price": 145, "rank": 4},
            "ripple": {"name": "XRP", "symbol": "XRP", "base_price": 0.58, "rank": 5},
        }
        results = []
        for coin_id_raw in coin_ids:
            coin_id = self._normalize_coin_id(coin_id_raw)
            coin_info = mock_data.get(coin_id, {"name": coin_id.title(), "symbol": coin_id[:4].upper(), "base_price": 100, "rank": 999})
            base_price = coin_info["base_price"]
            current_price = base_price * (1 + random.uniform(-0.05, 0.05))
            change_24h = random.uniform(-10, 10)
            results.append({
                "id": coin_id,
                "symbol": coin_info["symbol"],
                "name": coin_info["name"],
                "price": round(current_price, 8),
                "market_cap": round(current_price * random.randint(10000000, 100000000), 2),
                "volume_24h": round(current_price * random.randint(1000000, 10000000), 2),
                "change_24h": round(change_24h, 2),
                "rank": coin_info["rank"],
                "image": "",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "source": "coingecko_mock"
            })
        return results

    async def get_coin_details(self, coin_id: str) -> Optional[Dict[str, Any]]:
        coin_id = self._normalize_coin_id(coin_id)
        cached_details = await redis_cache.get_cached_coin_details(coin_id)
        if cached_details:
            return cached_details

        if self.use_mock:
            prices = self._get_mock_prices([coin_id])
            details = prices[0] if prices else None
            if details:
                await redis_cache.cache_coin_details(coin_id, details)
            return details

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/coins/{coin_id}",
                    params={"localization": "false", "tickers": "false", "market_data": "true", "community_data": "false", "developer_data": "false"}
                )
                response.raise_for_status()
                data = response.json()

            market = data.get("market_data", {})
            details = {
                "id": data.get("id"),
                "symbol": (data.get("symbol") or "").upper(),
                "name": data.get("name"),
                "price": float((market.get("current_price") or {}).get("usd") or 0),
                "market_cap": float((market.get("market_cap") or {}).get("usd") or 0),
                "volume_24h": float((market.get("total_volume") or {}).get("usd") or 0),
                "change_24h": round(float(market.get("price_change_percentage_24h") or 0), 2),
                "rank": int(data.get("market_cap_rank") or 0),
                "supply": float(market.get("circulating_supply") or 0),
                "max_supply": float(market.get("max_supply") or 0) if market.get("max_supply") else None,
                "vwap_24h": 0,
                "explorer": ((data.get("links") or {}).get("blockchain_site") or [""])[0],
                "image": ((data.get("image") or {}).get("large") or ""),
                "last_updated": market.get("last_updated") or datetime.now(timezone.utc).isoformat(),
                "source": "coingecko",
            }
            await redis_cache.cache_coin_details(coin_id, details)
            return details
        except Exception as e:
            logger.error("❌ Failed to fetch details for %s: %s", coin_id, str(e))
            return None

    async def get_price_history(self, coin_id: str, days: int = 7) -> List[Dict[str, Any]]:
        coin_id = self._normalize_coin_id(coin_id)
        if self.use_mock:
            return self._get_mock_history(coin_id, days)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/coins/{coin_id}/market_chart",
                    params={"vs_currency": "usd", "days": days, "interval": "hourly" if days <= 30 else "daily"},
                )
                response.raise_for_status()
                data = response.json()

            return [
                {"timestamp": int(point[0] / 1000), "price": float(point[1]), "date": datetime.utcfromtimestamp(point[0] / 1000).isoformat()}
                for point in data.get("prices", [])
            ]
        except Exception as e:
            logger.error("❌ Failed to fetch history for %s: %s", coin_id, str(e))
            return self._get_mock_history(coin_id, days)

    def _get_mock_history(self, coin_id: str, days: int) -> List[Dict[str, Any]]:
        base_price = 68000 if coin_id == "bitcoin" else 3500 if coin_id == "ethereum" else 100
        now = datetime.now(timezone.utc)
        history = []
        for i in range(days * 24):
            timestamp = now - timedelta(hours=days * 24 - i)
            price = base_price * (1 + random.uniform(-0.03, 0.03))
            history.append({"timestamp": int(timestamp.timestamp()), "price": round(price, 2), "date": timestamp.isoformat()})
        return history

    async def get_markets(self, coin_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        coin_id = self._normalize_coin_id(coin_id)
        if self.use_mock:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/coins/{coin_id}/tickers",
                    params={"page": 1},
                )
                response.raise_for_status()
                data = response.json()
            markets = data.get("tickers", [])[:limit]
            return [
                {
                    "exchange": (m.get("market") or {}).get("name", ""),
                    "pair": f"{m.get('base', '')}/{m.get('target', '')}",
                    "price": float(m.get("last") or 0),
                    "volume_24h": float((m.get("converted_volume") or {}).get("usd") or 0),
                    "volume_percent": 0,
                }
                for m in markets
            ]
        except Exception as e:
            logger.error("❌ Failed to fetch markets for %s: %s", coin_id, str(e))
            return []

    async def search_assets(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if self.use_mock:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/search", params={"query": query})
                response.raise_for_status()
                data = response.json()
            coins = data.get("coins", [])[:limit]
            return [
                {
                    "id": c.get("id"),
                    "symbol": (c.get("symbol") or "").upper(),
                    "name": c.get("name"),
                    "rank": int(c.get("market_cap_rank") or 0),
                    "price": 0.0,
                    "image": c.get("thumb") or "",
                }
                for c in coins
            ]
        except Exception as e:
            logger.error("❌ Failed to search assets: %s", str(e))
            return []


coincap_service = CoinCapService()
