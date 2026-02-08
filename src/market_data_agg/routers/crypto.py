"""Cryptocurrency market data routes (CoinGecko)."""
from fastapi import APIRouter, Query, WebSocket

from market_data_agg.deps import MarketsServiceDep
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/crypto", tags=["crypto"])


@router.websocket("/stream")
async def stream_crypto(websocket: WebSocket, service: MarketsServiceDep) -> None:
    """Stream real-time crypto quotes. Query param: ?symbols=bitcoin,ethereum,solana"""
    await service.handle_crypto_websocket(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=bitcoin,ethereum)",
    )


@router.get("/overview", response_model=list[MarketQuote])
async def get_crypto_overview(service: MarketsServiceDep) -> list[MarketQuote]:
    """Get overview (top by market cap) crypto quotes."""
    return await service.get_crypto_overview()


@router.get("/{symbol}", response_model=MarketQuote)
async def get_crypto_quote(symbol: str, service: MarketsServiceDep) -> MarketQuote:
    """Get the current quote for a cryptocurrency (CoinGecko ID, e.g. bitcoin, ethereum)."""
    return await service.get_crypto_quote(symbol)


@router.get("/{symbol}/history", response_model=list[MarketQuote])
async def get_crypto_history(
    service: MarketsServiceDep,
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
) -> list[MarketQuote]:
    """Get historical data for a cryptocurrency."""
    return await service.get_crypto_history(symbol, days)


@router.post("/refresh")
async def refresh_crypto(service: MarketsServiceDep) -> dict[str, str]:
    """Force refresh the crypto data provider."""
    await service.refresh_crypto()
    return {"status": "refreshed"}
