"""Stock market data routes (Yahoo Finance)."""
# TODO: Move business logic (provider calls, mapping) into a stocks service layer.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO: Consider API gateway (rate limiting, routing) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive/refresh endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
from datetime import datetime, timedelta
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query

from market_data_agg.providers import YFinanceProvider
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/stocks", tags=["stocks"])


@lru_cache
def get_provider() -> YFinanceProvider:
    """Get singleton YFinance provider instance."""
    return YFinanceProvider()


@router.get("/{symbol}", response_model=MarketQuote)
async def get_stock_quote(
    symbol: str,
    provider: YFinanceProvider = Depends(get_provider),
) -> MarketQuote:
    """Get the current quote for a stock symbol.

    Args:
        symbol: Stock ticker (e.g., "AAPL", "MSFT", "GOOGL").

    Returns:
        Current market quote with price and metadata.
    """
    try:
        return await provider.get_quote(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found: {e}")


@router.get("/{symbol}/history", response_model=list[MarketQuote])
async def get_stock_history(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    provider: YFinanceProvider = Depends(get_provider),
) -> list[MarketQuote]:
    """Get historical data for a stock symbol.

    Args:
        symbol: Stock ticker.
        days: Number of days of history (default: 30, max: 365).

    Returns:
        List of historical quotes ordered by timestamp.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    try:
        return await provider.get_history(symbol.upper(), start, end)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"History for {symbol} not found: {e}")


@router.post("/refresh")
async def refresh_stocks(
    provider: YFinanceProvider = Depends(get_provider),
) -> dict[str, str]:
    """Force refresh the stock data provider.

    No-op for YFinance (no persistent connections or cache).
    """
    await provider.refresh()
    return {"status": "refreshed"}
