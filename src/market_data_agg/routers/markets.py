"""Aggregated market views across all providers."""
from fastapi import APIRouter, Query

from market_data_agg.deps import MarketsServiceDep
from market_data_agg.db import Source
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/overview", response_model=list[MarketQuote])
async def get_market_overview(service: MarketsServiceDep) -> list[MarketQuote]:
    """Overview of quotes across stocks, crypto, and prediction markets. Failed providers omitted."""
    return await service.get_overview()


@router.get("/top-movers", response_model=list[MarketQuote])
async def get_top_movers(
    service: MarketsServiceDep,
    source: Source | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
) -> list[MarketQuote]:
    """Top movers by absolute 24h change; optional filter by source."""
    return await service.get_top_movers(source=source, limit=limit)
