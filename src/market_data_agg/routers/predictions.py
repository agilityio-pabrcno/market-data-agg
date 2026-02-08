"""Prediction market routes (single provider)."""

from fastapi import APIRouter, Query, WebSocket

from market_data_agg.deps import MarketsServiceDep
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.websocket("/stream")
async def stream_predictions(
    websocket: WebSocket,
    service: MarketsServiceDep,
) -> None:
    """Stream real-time quotes. Query param: ?symbols=slug-1,slug-2"""
    await service.handle_predictions_websocket(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=market-slug-1,market-slug-2)",
    )


@router.get("/overview", response_model=list[MarketQuote])
async def get_predictions_overview(service: MarketsServiceDep) -> list[MarketQuote]:
    """Overview (active markets) from the prediction provider."""
    return await service.get_predictions_overview()


@router.get("/markets", response_model=list[MarketQuote])
async def list_markets(
    service: MarketsServiceDep,
    active: bool = Query(default=True, description="Filter for active markets only"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum markets to return"),
    tag_id: str | None = Query(default=None, description="Filter by tag/category ID"),
) -> list[MarketQuote]:
    """List available markets."""
    return await service.list_prediction_markets(
        active=active, limit=limit, tag_id=tag_id
    )


@router.get("/markets/{market_id}", response_model=MarketQuote)
async def get_market(
    market_id: str,
    service: MarketsServiceDep,
) -> MarketQuote:
    """Get details for a specific market (slug or condition ID)."""
    return await service.get_prediction_quote(market_id)


@router.post("/refresh")
async def refresh_predictions(service: MarketsServiceDep) -> dict[str, str]:
    """Force refresh the prediction provider."""
    await service.refresh_predictions()
    return {"status": "refreshed"}
