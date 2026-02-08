"""Stock market data routes (Yahoo Finance)."""
from fastapi import APIRouter, Query, WebSocket

from market_data_agg.deps import MarketsServiceDep
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/overview", response_model=list[MarketQuote])
async def get_stocks_overview(service: MarketsServiceDep) -> list[MarketQuote]:
    """Get overview (main) stock quotes. Returns the provider's default set of top stocks."""
    return await service.get_stocks_overview()


@router.get("/{symbol}", response_model=MarketQuote)
async def get_stock_quote(symbol: str, service: MarketsServiceDep) -> MarketQuote:
    """Get the current quote for a stock symbol (e.g. AAPL, MSFT, GOOGL)."""
    return await service.get_stock_quote(symbol)


@router.get("/{symbol}/history", response_model=list[MarketQuote])
async def get_stock_history(
    service: MarketsServiceDep,
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
) -> list[MarketQuote]:
    """Get historical data for a stock symbol."""
    return await service.get_stock_history(symbol, days)


@router.post("/refresh")
async def refresh_stocks(service: MarketsServiceDep) -> dict[str, str]:
    """Force refresh the stock data provider (no-op for YFinance)."""
    await service.refresh_stocks()
    return {"status": "refreshed"}


@router.websocket("/stream")
async def stream_stocks(websocket: WebSocket, service: MarketsServiceDep) -> None:
    """Stream real-time stock quotes. Query param: ?symbols=AAPL,MSFT,GOOGL"""
    await service.handle_stocks_websocket(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=AAPL,MSFT)",
    )
