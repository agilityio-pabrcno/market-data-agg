"""Aggregated market views across all providers.

Most orchestration (gathering provider overviews, combining results, top-movers
sorting) will live in a markets service layer; this router should only call
the service and return responses.
"""
# TODO: Introduce a markets service layer: move overview aggregation (gather +
#       flatten), top-movers (gather by source, sort by change_24h), and any
#       future aggregation logic there; keep this module as thin HTTP handlers.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO:  API gateway (rate limiting, routing) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
import asyncio
import logging

from fastapi import APIRouter, Depends, Query

logger = logging.getLogger(__name__)

from market_data_agg.db import Source
from market_data_agg.dependencies import (get_crypto_provider,
                                          get_predictions_provider,
                                          get_stocks_provider)
from market_data_agg.providers import MarketProviderABC, PredictionsProviderABC
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/overview", response_model=list[MarketQuote])
async def get_market_overview(
    stocks_provider: MarketProviderABC = Depends(get_stocks_provider),
    crypto_provider: MarketProviderABC = Depends(get_crypto_provider),
    predictions_provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> list[MarketQuote]:
    """Get an overview of quotes across all market types.

    Returns a snapshot of each provider's main/top quotes (stocks, crypto, prediction markets).
    If a provider fails (e.g. rate limit), its results are omitted and the rest are returned.
    """
    # TODO: Move this logic to a markets service layer.
    results = await asyncio.gather(
        stocks_provider.get_overview_quotes(),
        crypto_provider.get_overview_quotes(),
        predictions_provider.get_overview_quotes(),
        return_exceptions=True,
    )
    quotes: list[MarketQuote] = []
    for name, result in zip(("stocks", "crypto", "predictions"), results):
        if isinstance(result, Exception):
            logger.warning("Markets overview: %s provider failed: %s", name, result)
            continue
        quotes.extend(result)
    return quotes


def _change_24h(q: MarketQuote) -> float:
    """Helper for sorting by 24h change."""
    # TODO: Move this logic to a markets service layer.
    if q.metadata and "change_24h" in q.metadata:
        val = q.metadata["change_24h"]
        return abs(val) if val is not None else 0.0
    return 0.0


@router.get("/top-movers", response_model=list[MarketQuote])
async def get_top_movers(
    source: Source | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    stocks_provider: MarketProviderABC = Depends(get_stocks_provider),
    crypto_provider: MarketProviderABC = Depends(get_crypto_provider),
    predictions_provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> list[MarketQuote]:
    """Get top movers based on 24h change.

    Uses each provider's overview quotes; sorts by absolute 24h change.
    If a provider fails when source is None, its results are omitted.
    """
    # TODO: Move this logic to a markets service layer.
    if source is None:
        results = await asyncio.gather(
            stocks_provider.get_overview_quotes(),
            crypto_provider.get_overview_quotes(),
            predictions_provider.get_overview_quotes(),
            return_exceptions=True,
        )
        quotes = []
        for name, result in zip(("stocks", "crypto", "predictions"), results):
            if isinstance(result, Exception):
                logger.warning("Top movers: %s provider failed: %s", name, result)
                continue
            quotes.extend(result)
    elif source == Source.STOCK:
        quotes = await stocks_provider.get_overview_quotes()
    elif source == Source.CRYPTO:
        quotes = await crypto_provider.get_overview_quotes()
    else:
        quotes = await predictions_provider.get_overview_quotes()

    quotes.sort(key=_change_24h, reverse=True)
    return quotes[:limit]
