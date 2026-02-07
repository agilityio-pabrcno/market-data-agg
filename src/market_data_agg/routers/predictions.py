"""Prediction market routes (Polymarket, Kalshi, etc.).

Provider-specific routes use /predictions/{provider}/...
Aggregate routes: /predictions, /predictions/overview.
"""
# Route order: static paths before /{provider}/... so they match first.

from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, WebSocket

from market_data_agg.container import (
    Container,
    get_prediction_providers,
    get_prediction_service,
    get_prediction_service_ws,
)
from market_data_agg.schemas import MarketQuote
from market_data_agg.services import MarketService, MarketsService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("")
async def list_providers(
    providers: list[str] = Depends(get_prediction_providers),
) -> dict[str, list[str]]:
    """List available prediction providers (e.g. polymarket, kalshi)."""
    return {"providers": providers}


@router.get("/overview", response_model=list[MarketQuote])
@inject
async def get_predictions_overview(
    service: Annotated[MarketsService, Depends(Provide[Container.markets_service])],
) -> list[MarketQuote]:
    """Overview (active markets) from all prediction providers."""
    return await service.get_predictions_overview()


@router.websocket("/{provider}/stream")
async def stream_predictions(
    websocket: WebSocket,
    service: MarketService = Depends(get_prediction_service_ws),
) -> None:
    """Stream real-time quotes. Query param: ?symbols=slug-1,slug-2"""
    await service.handle_websocket_stream(
        websocket,
        "Query param 'symbols' required (e.g. ?symbols=market-slug-1,market-slug-2)",
    )


@router.get("/{provider}/overview", response_model=list[MarketQuote])
async def get_provider_overview(
    service: MarketService = Depends(get_prediction_service),
) -> list[MarketQuote]:
    """Overview (active markets) from a specific provider."""
    return await service.get_overview_quotes()


@router.get("/{provider}/markets", response_model=list[MarketQuote])
async def list_markets(
    service: MarketService = Depends(get_prediction_service),
    active: bool = Query(default=True, description="Filter for active markets only"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum markets to return"),
    tag_id: str | None = Query(default=None, description="Filter by tag/category ID"),
) -> list[MarketQuote]:
    """List available markets from a specific provider."""
    return await service.list_markets(active=active, limit=limit, tag_id=tag_id)


@router.get("/{provider}/markets/{market_id}", response_model=MarketQuote)
async def get_market(
    market_id: str,
    service: MarketService = Depends(get_prediction_service),
) -> MarketQuote:
    """Get details for a specific market (slug or condition ID)."""
    return await service.get_quote(market_id)


@router.post("/{provider}/refresh")
async def refresh_predictions(
    service: MarketService = Depends(get_prediction_service),
) -> dict[str, str]:
    """Force refresh the provider."""
    await service.refresh()
    return {"status": "refreshed"}
