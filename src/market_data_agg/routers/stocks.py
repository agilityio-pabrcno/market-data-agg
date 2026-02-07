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
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from market_data_agg.dependencies import get_stocks_provider
from market_data_agg.providers import MarketProviderABC
from market_data_agg.schemas import MarketQuote

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/overview", response_model=list[MarketQuote])
async def get_stocks_overview(
    provider: MarketProviderABC = Depends(get_stocks_provider),
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
    provider: MarketProviderABC = Depends(get_stocks_provider),
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
    provider: MarketProviderABC = Depends(get_stocks_provider),
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
    provider: MarketProviderABC = Depends(get_stocks_provider),
) -> dict[str, str]:
    """Force refresh the stock data provider.

    No-op for YFinance (no persistent connections or cache).
    """
    # TODO: Service layer will own: refresh orchestration and response shape.
    await provider.refresh()
    return {"status": "refreshed"}


@router.websocket("/stream")
async def stream_stocks(websocket: WebSocket) -> None:
    """Stream real-time stock quotes over WebSocket.

    Uses the stocks provider's polling-based stream. Pass symbols as query param:
    /stocks/stream?symbols=AAPL,MSFT,GOOGL
    Each message is a MarketQuote JSON (source=stock).
    """
    await websocket.accept()
    symbols_param = (websocket.query_params.get("symbols") or "").strip()
    symbol_list = [s.strip().upper() for s in symbols_param.split(",") if s.strip()]
    if not symbol_list:
        await websocket.close(code=4000, reason="Query param 'symbols' required (e.g. ?symbols=AAPL,MSFT)")
        return
    provider = websocket.scope["app"].state.stocks_provider
    try:
        async for quote in provider.stream(symbol_list):
            await websocket.send_json(quote.model_dump(mode="json"))
    except WebSocketDisconnect:
        logger.debug("Stocks stream client disconnected")
    except Exception as exc:
        logger.exception("Stocks stream error: %s", exc)
        try:
            await websocket.close(code=1011, reason="Stream error")
        except Exception:
            pass
