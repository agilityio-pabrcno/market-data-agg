"""Aggregated market views across all providers.

Thin HTTP handlers; aggregation logic lives in MarketsService.
"""
from fastapi import APIRouter, Depends, Query

from market_data_agg.db import Source
from market_data_agg.dependencies import get_markets_service
from market_data_agg.schemas import MarketQuote
from market_data_agg.services import MarketsService

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/overview", response_model=list[MarketQuote])
async def get_market_overview(
    service: MarketsService = Depends(get_markets_service),
) -> list[MarketQuote]:
    """Overview of quotes across stocks, crypto, and prediction markets. Failed providers omitted."""
    return await service.get_overview()


@router.get("/top-movers", response_model=list[MarketQuote])
async def get_top_movers(
    source: Source | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    service: MarketsService = Depends(get_markets_service),
) -> list[MarketQuote]:
    """Top movers by absolute 24h change; optional filter by source."""
    return await service.get_top_movers(source=source, limit=limit)
