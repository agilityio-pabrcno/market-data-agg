"""Aggregated market views across all providers.

Most orchestration (gathering provider overviews, combining results, top-movers
sorting) will live in a markets service layer; this router should only call
the service and return responses.
"""
# TODO: Introduce a markets service layer: move overview aggregation (gather +
#       flatten), top-movers (gather by source, sort by change_24h), and any
#       future aggregation logic there; keep this module as thin HTTP handlers.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO: Consider API gateway (rate limiting, routing) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
import asyncio

from fastapi import APIRouter, Depends, Query

from market_data_agg.db import Source
from market_data_agg.dependencies import (get_crypto_provider,
                                          get_predictions_provider,
                                          get_stocks_provider)
from market_data_agg.providers import (CryptoProviderABC,
                                       PredictionsProviderABC,
                                       StocksProviderABC)
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/markets", tags=["markets"])

# Routes are static (/overview, /top-movers); no path params, so order is flexible.


@router.get("/overview", response_model=list[MarketQuote])
async def get_market_overview(
    stocks_provider: StocksProviderABC = Depends(get_stocks_provider),
    crypto_provider: CryptoProviderABC = Depends(get_crypto_provider),
    predictions_provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> list[MarketQuote]:
    """Get an overview of quotes across all market types.

    Returns a snapshot of each provider's main/top quotes (stocks, crypto, prediction markets).
    """
    # Service layer will own: asyncio.gather of all three get_overview_quotes(), flatten, and error handling.
    stocks, crypto, predictions = await asyncio.gather(
        stocks_provider.get_overview_quotes(),
        crypto_provider.get_overview_quotes(),
        predictions_provider.get_overview_quotes(),
    )
    return list(stocks) + list(crypto) + list(predictions)


# Service layer will own this helper (sort key for 24h change).
def _change_24h(q: MarketQuote) -> float:
    if q.metadata and "change_24h" in q.metadata:
        val = q.metadata["change_24h"]
        return abs(val) if val is not None else 0.0
    return 0.0


@router.get("/top-movers", response_model=list[MarketQuote])
async def get_top_movers(
    source: Source | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    stocks_provider: StocksProviderABC = Depends(get_stocks_provider),
    crypto_provider: CryptoProviderABC = Depends(get_crypto_provider),
    predictions_provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> list[MarketQuote]:
    """Get top movers based on 24h change.

    Uses each provider's overview quotes; sorts by absolute 24h change.
    """
    # Service layer will own: source-based gather (or single provider), _change_24h sort, and limit.
    if source is None:
        stocks, crypto, predictions = await asyncio.gather(
            stocks_provider.get_overview_quotes(),
            crypto_provider.get_overview_quotes(),
            predictions_provider.get_overview_quotes(),
        )
        quotes = list(stocks) + list(crypto) + list(predictions)
    elif source == Source.STOCK:
        quotes = await stocks_provider.get_overview_quotes()
    elif source == Source.CRYPTO:
        quotes = await crypto_provider.get_overview_quotes()
    else:
        quotes = await predictions_provider.get_overview_quotes()

    quotes.sort(key=_change_24h, reverse=True)
    return quotes[:limit]
