"""Portfolio management endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

from models import Portfolio, Holding, HoldingCreate
from dependencies import get_current_user_id, get_db
from cache import cache
from redis_cache import redis_cache
from services import price_stream_service
from coincap_service import coincap_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# ============================================
# HELPER FUNCTIONS
# ============================================

async def get_price_for_symbol(symbol: str) -> Optional[float]:
    """
    Get current price for a symbol from Redis cache.
    Falls back to in-memory cache if Redis unavailable.
    """
    try:
        # Try Redis first
        cache_key = f"crypto:price:{symbol.lower()}"
        cached_price = await redis_cache.get(cache_key)

        if cached_price:
            return float(cached_price)

        # Fall back to in-memory cache from price stream service
        if symbol in price_stream_service.prices:
            return price_stream_service.prices[symbol]

        return None

    except Exception as e:
        logger.warning(f"⚠️ Error getting price for {symbol}: {e}")
        return None


# ============================================
# ENDPOINTS
# ============================================

@router.get("")
@cache(ttl=60)
async def get_portfolio(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get user's complete portfolio with real-time prices from Redis cache."""
    portfolios_collection = db.get_collection("portfolios")
    portfolio_doc = await portfolios_collection.find_one({"user_id": user_id})

    if not portfolio_doc:
        portfolio = Portfolio(user_id=user_id)
        await portfolios_collection.insert_one(portfolio.dict())
        return {"portfolio": {"totalBalance": 0, "holdings": []}}

    holdings = portfolio_doc.get("holdings", [])
    total_balance = 0
    updated_holdings = []

    # Batch get prices from Redis
    symbols = [h.get("symbol", "").lower() for h in holdings]
    price_keys = [f"crypto:price:{s}" for s in symbols]
    cached_prices = await redis_cache.mget(price_keys) if price_keys else []

    price_map = {symbol: float(price) if price else None for symbol, price in zip(symbols, cached_prices)}

    for holding in holdings:
        symbol = holding.get("symbol", "").upper()
        symbol_lower = symbol.lower()
        current_price = price_map.get(symbol_lower) or price_stream_service.prices.get(symbol)

        if current_price is not None and current_price > 0:
            current_value = holding.get("amount", 0) * current_price
            total_balance += current_value
            updated_holdings.append({
                "symbol": symbol,
                "name": holding.get("name", symbol),
                "amount": holding.get("amount", 0),
                "current_price": current_price,
                "value": round(current_value, 2),
                "allocation": 0,
                "cached_at": datetime.now(timezone.utc).isoformat()
            })
        else:
            updated_holdings.append({
                "symbol": symbol,
                "name": holding.get("name", symbol),
                "amount": holding.get("amount", 0),
                "current_price": 0,
                "value": 0,
                "allocation": 0,
                "cached_at": None
            })

    # Calculate allocations
    for h in updated_holdings:
        h["allocation"] = round((h["value"] / total_balance * 100), 2) if total_balance > 0 else 0

    # Log portfolio calculation
    logger.info(f"📊 Portfolio calculated for user {user_id}: ${total_balance:.2f} ({len(updated_holdings)} holdings)")

    return {
        "portfolio": {
            "totalBalance": round(total_balance, 2),
            "holdings": updated_holdings
        }
    }


@router.get("/holding/{symbol}")
async def get_holding(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Get specific holding by symbol."""
    portfolios_collection = db.get_collection("portfolios")
    portfolio_doc = await portfolios_collection.find_one({"user_id": user_id})
    if not portfolio_doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = portfolio_doc.get("holdings", [])
    holding = next((h for h in holdings if h["symbol"] == symbol.upper()), None)

    if not holding:
        raise HTTPException(status_code=404, detail="Holding not found")

    return {"holding": holding}


@router.post("/holding")
async def add_holding(
    holding_data: HoldingCreate,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Add or update holding in portfolio."""
    portfolios_collection = db.get_collection("portfolios")
    portfolio_doc = await portfolios_collection.find_one({"user_id": user_id})

    if not portfolio_doc:
        portfolio = Portfolio(user_id=user_id)
        await portfolios_collection.insert_one(portfolio.dict())
        holdings = []
    else:
        holdings = portfolio_doc.get("holdings", [])

    prices = await coincap_service.get_prices()
    crypto = next((c for c in prices if c["symbol"].upper() == holding_data.symbol.upper()), None)
    if not crypto:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")

    # Safely extract price from crypto data
    price = crypto.get("price")
    if price is None or price <= 0:
        raise HTTPException(status_code=500, detail="Cryptocurrency price unavailable or invalid")

    new_holding = {
        "symbol": holding_data.symbol.upper(),
        "name": holding_data.name,
        "amount": holding_data.amount,
        "value": round(holding_data.amount * price, 2),
        "allocation": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    existing_idx = next((i for i, h in enumerate(holdings) if h["symbol"] == holding_data.symbol.upper()), None)

    if existing_idx is not None:
        holdings[existing_idx]["amount"] += holding_data.amount
        holdings[existing_idx]["value"] = round(holdings[existing_idx]["amount"] * price, 2)
    else:
        holdings.append(new_holding)

    logger.info(f"✅ Holding added for {holding_data.symbol}: {holding_data.amount} @ ${price}")

    await portfolios_collection.update_one(
        {"user_id": user_id},
        {"$set": {"holdings": holdings, "updated_at": datetime.now(timezone.utc)}}
    )

    # Invalidate portfolio cache
    await redis_cache.delete(f"portfolio:{user_id}")

    return {"message": "Holding added successfully", "holding": new_holding}


@router.delete("/holding/{symbol}")
async def delete_holding(
    symbol: str,
    user_id: str = Depends(get_current_user_id),
    db = Depends(get_db)
):
    """Delete holding from portfolio."""
    portfolios_collection = db.get_collection("portfolios")
    portfolio_doc = await portfolios_collection.find_one({"user_id": user_id})
    if not portfolio_doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    holdings = portfolio_doc.get("holdings", [])
    holdings = [h for h in holdings if h["symbol"] != symbol.upper()]

    await portfolios_collection.update_one(
        {"user_id": user_id},
        {"$set": {"holdings": holdings, "updated_at": datetime.now(timezone.utc)}}
    )

    # Invalidate portfolio cache
    await redis_cache.delete(f"portfolio:{user_id}")

    return {"message": "Holding deleted successfully"}
