"""Prediction market routes (Polymarket provider).

Thin HTTP handlers; business logic and error mapping live in PredictionsService.
"""
# Route order: /overview and /stream before /markets so they are matched first.

from fastapi import APIRouter, Depends, Query, WebSocket

from market_data_agg.dependencies import get_predictions_service
from market_data_agg.schemas import MarketQuote
from market_data_agg.services import PredictionsService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.websocket("/stream")
async def stream_predictions(websocket: WebSocket) -> None:
    """Stream real-time prediction market quotes. Query param: ?symbols=market-slug-1,market-slug-2"""
    app = websocket.scope["app"]
    service = PredictionsService(app.state.predictions_provider)
    await service.handle_websocket_stream(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=market-slug-1,market-slug-2)",
    )


@router.get("/overview", response_model=list[MarketQuote])
async def get_predictions_overview(
    service: PredictionsService = Depends(get_predictions_service),
) -> list[MarketQuote]:
    """Get overview (active) prediction markets."""
    return await service.get_overview_quotes()


@router.get("/markets", response_model=list[MarketQuote])
async def list_markets(
    active: bool = Query(default=True, description="Filter for active markets only"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum markets to return"),
    tag_id: str | None = Query(default=None, description="Filter by tag/category ID"),
    service: PredictionsService = Depends(get_predictions_service),
) -> list[MarketQuote]:
    """List available prediction markets (active, limit, optional tag_id)."""
    return await service.list_markets(active=active, limit=limit, tag_id=tag_id)


@router.get("/markets/{market_id}", response_model=MarketQuote)
async def get_market(
    market_id: str,
    service: PredictionsService = Depends(get_predictions_service),
) -> MarketQuote:
    """Get details for a specific prediction market (slug or condition ID)."""
    return await service.get_quote(market_id)


@router.post("/refresh")
async def refresh_predictions(
    service: PredictionsService = Depends(get_predictions_service),
) -> dict[str, str]:
    """Force refresh the predictions provider."""
    await service.refresh()
    return {"status": "refreshed"}
