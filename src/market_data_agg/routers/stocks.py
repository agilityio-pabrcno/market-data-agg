"""Stock market data routes (Yahoo Finance).

Quote/history/overview/refresh logic will live in a stocks service layer;
this router should only call the service and return responses.
"""
# TODO: Introduce a stocks service layer: move get_quote, get_history,
#       get_overview_quotes, and refresh handling there; keep this module as thin HTTP handlers.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO: API gateway (rate limiting, routing) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive/refresh endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from market_data_agg.dependencies import get_stocks_provider
from market_data_agg.providers import StocksProviderABC
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/overview", response_model=list[MarketQuote])
async def get_stocks_overview(
    provider: StocksProviderABC = Depends(get_stocks_provider),
) -> list[MarketQuote]:
    """Get overview (main) stock quotes.

    Returns the provider's default set of top stocks.
    """
    # TODO: Service layer will own: calling provider.get_overview_quotes() and error handling.
    try:
        return await provider.get_overview_quotes()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch overview: {e}") from e


@router.get("/{symbol}", response_model=MarketQuote)
async def get_stock_quote(
    symbol: str,
    provider: StocksProviderABC = Depends(get_stocks_provider),
) -> MarketQuote:
    """Get the current quote for a stock symbol.

    Args:
        symbol: Stock ticker (e.g., "AAPL", "MSFT", "GOOGL").

    Returns:
        Current market quote with price and metadata.
    """
    # TODO: Service layer will own: get_quote(symbol), normalization, and 404 mapping.
    try:
        return await provider.get_quote(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found: {e}")


@router.get("/{symbol}/history", response_model=list[MarketQuote])
async def get_stock_history(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    provider: StocksProviderABC = Depends(get_stocks_provider),
) -> list[MarketQuote]:
    """Get historical data for a stock symbol.

    Args:
        symbol: Stock ticker.
        days: Number of days of history (default: 30, max: 365).

    Returns:
        List of historical quotes ordered by timestamp.
    """
    # TODO: Service layer will own: date range (days → start/end), get_history(), and error mapping.
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    try:
        return await provider.get_history(symbol.upper(), start, end)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"History for {symbol} not found: {e}")


@router.post("/refresh")
async def refresh_stocks(
    provider: StocksProviderABC = Depends(get_stocks_provider),
) -> dict[str, str]:
    """Force refresh the stock data provider.

    No-op for YFinance (no persistent connections or cache).
    """
    # TODO: Service layer will own: refresh orchestration and response shape.
    await provider.refresh()
    return {"status": "refreshed"}
