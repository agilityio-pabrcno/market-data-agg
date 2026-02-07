"""Cryptocurrency market data routes (CoinGecko)."""
from fastapi import APIRouter, Query, WebSocket

from market_data_agg.deps import CryptoService
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/crypto", tags=["crypto"])


@router.websocket("/stream")
async def stream_crypto(websocket: WebSocket, service: CryptoService) -> None:
    """Stream real-time crypto quotes. Query param: ?symbols=bitcoin,ethereum,solana"""
    await service.handle_websocket_stream(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=bitcoin,ethereum)",
    )


@router.get("/overview", response_model=list[MarketQuote])
async def get_crypto_overview(service: CryptoService) -> list[MarketQuote]:
    """Get overview (top by market cap) crypto quotes."""
    return await service.get_overview_quotes()


@router.get("/{symbol}", response_model=MarketQuote)
async def get_crypto_quote(symbol: str, service: CryptoService) -> MarketQuote:
    """Get the current quote for a cryptocurrency (CoinGecko ID, e.g. bitcoin, ethereum)."""
    return await service.get_quote(symbol)


@router.get("/{symbol}/history", response_model=list[MarketQuote])
async def get_crypto_history(
    service: CryptoService,
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
) -> list[MarketQuote]:
    """Get historical data for a cryptocurrency."""
    return await service.get_history(symbol, days)


@router.post("/refresh")
async def refresh_crypto(service: CryptoService) -> dict[str, str]:
    """Force refresh the crypto data provider."""
    await service.refresh()
    return {"status": "refreshed"}
