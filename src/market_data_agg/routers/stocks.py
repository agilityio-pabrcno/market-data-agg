"""Stock market data routes (Yahoo Finance).

Thin HTTP handlers; business logic and error mapping live in StocksService.
"""
from fastapi import APIRouter, Depends, Query, WebSocket

from market_data_agg.dependencies import get_stocks_service
from market_data_agg.schemas import MarketQuote
from market_data_agg.services import StocksService

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/overview", response_model=list[MarketQuote])
async def get_stocks_overview(
    service: StocksService = Depends(get_stocks_service),
) -> list[MarketQuote]:
    """Get overview (main) stock quotes. Returns the provider's default set of top stocks."""
    return await service.get_overview_quotes()


@router.get("/{symbol}", response_model=MarketQuote)
async def get_stock_quote(
    symbol: str,
    service: StocksService = Depends(get_stocks_service),
) -> MarketQuote:
    """Get the current quote for a stock symbol (e.g. AAPL, MSFT, GOOGL)."""
    return await service.get_quote(symbol)


@router.get("/{symbol}/history", response_model=list[MarketQuote])
async def get_stock_history(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    service: StocksService = Depends(get_stocks_service),
) -> list[MarketQuote]:
    """Get historical data for a stock symbol."""
    return await service.get_history(symbol, days)


@router.post("/refresh")
async def refresh_stocks(
    service: StocksService = Depends(get_stocks_service),
) -> dict[str, str]:
    """Force refresh the stock data provider (no-op for YFinance)."""
    await service.refresh()
    return {"status": "refreshed"}


@router.websocket("/stream")
async def stream_stocks(websocket: WebSocket) -> None:
    """Stream real-time stock quotes. Query param: ?symbols=AAPL,MSFT,GOOGL"""
    app = websocket.scope["app"]
    service = StocksService(app.state.stocks_provider)
    await service.handle_websocket_stream(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=AAPL,MSFT)",
    )
