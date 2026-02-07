"""Stock market data routes (Yahoo Finance)."""
from dependency_injector.wiring import inject
from fastapi import APIRouter, Query, WebSocket

from market_data_agg.container import StocksService
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/overview", response_model=list[MarketQuote])
@inject
async def get_stocks_overview(service: StocksService) -> list[MarketQuote]:
    """Get overview (main) stock quotes. Returns the provider's default set of top stocks."""
    return await service.get_overview_quotes()


@router.get("/{symbol}", response_model=MarketQuote)
@inject
async def get_stock_quote(symbol: str, service: StocksService) -> MarketQuote:
    """Get the current quote for a stock symbol (e.g. AAPL, MSFT, GOOGL)."""
    return await service.get_quote(symbol)


@router.get("/{symbol}/history", response_model=list[MarketQuote])
@inject
async def get_stock_history(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    service: StocksService = None,
) -> list[MarketQuote]:
    """Get historical data for a stock symbol."""
    return await service.get_history(symbol, days)


@router.post("/refresh")
@inject
async def refresh_stocks(service: StocksService) -> dict[str, str]:
    """Force refresh the stock data provider (no-op for YFinance)."""
    await service.refresh()
    return {"status": "refreshed"}


@router.websocket("/stream")
@inject
async def stream_stocks(websocket: WebSocket, service: StocksService) -> None:
    """Stream real-time stock quotes. Query param: ?symbols=AAPL,MSFT,GOOGL"""
    await service.handle_websocket_stream(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=AAPL,MSFT)",
    )
