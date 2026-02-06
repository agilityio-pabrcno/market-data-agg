"""Aggregated market views across all providers."""
# TODO: Move aggregation logic into a markets service layer (orchestrate providers).
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO: Consider API gateway (rate limiting, routing) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
from functools import lru_cache

import httpx
from fastapi import APIRouter, Depends, Query

from market_data_agg.db import Source
from market_data_agg.providers import YFinanceProvider, CoinGeckoProvider, PolymarketProvider
from market_data_agg.schemas import MarketQuote

router = APIRouter(prefix="/markets", tags=["markets"])

# Default symbols for overview
DEFAULT_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
DEFAULT_CRYPTO = ["bitcoin", "ethereum", "solana"]


@lru_cache
def get_stocks_provider() -> YFinanceProvider:
    """Get singleton YFinance provider."""
    return YFinanceProvider()


@lru_cache
def get_coingecko() -> CoinGeckoProvider:
    """Get singleton CoinGecko provider."""
    return CoinGeckoProvider()


@lru_cache
def get_polymarket() -> PolymarketProvider:
    """Get singleton Polymarket provider."""
    return PolymarketProvider()


@router.get("/overview", response_model=list[MarketQuote])
async def get_market_overview(
    include_stocks: bool = Query(default=True, description="Include stock quotes"),
    include_crypto: bool = Query(default=True, description="Include crypto quotes"),
    include_polymarket: bool = Query(default=True, description="Include prediction markets"),
    polymarket_limit: int = Query(default=5, ge=1, le=20, description="Max prediction markets"),
    stocks_provider: YFinanceProvider = Depends(get_stocks_provider),
    coingecko: CoinGeckoProvider = Depends(get_coingecko),
    polymarket: PolymarketProvider = Depends(get_polymarket),
) -> list[MarketQuote]:
    """Get an overview of quotes across all market types.

    Returns a snapshot of key stocks, crypto, and prediction markets.

    Args:
        include_stocks: Include top stock quotes.
        include_crypto: Include top crypto quotes.
        include_polymarket: Include active prediction markets.
        polymarket_limit: Max prediction markets to include.

    Returns:
        Combined list of quotes from all sources.
    """
    quotes: list[MarketQuote] = []

    # Fetch stocks
    if include_stocks:
        for symbol in DEFAULT_STOCKS:
            try:
                quote = await stocks_provider.get_quote(symbol)
                quotes.append(quote)
            except (httpx.HTTPError, ValueError, KeyError):
                pass  # Skip unavailable

    # Fetch crypto
    if include_crypto:
        for symbol in DEFAULT_CRYPTO:
            try:
                quote = await coingecko.get_quote(symbol)
                quotes.append(quote)
            except (httpx.HTTPError, ValueError, KeyError):
                pass  # Skip unavailable

    # Fetch prediction markets
    if include_polymarket:
        try:
            markets = await polymarket.list_markets(active=True, limit=polymarket_limit)
            quotes.extend(markets)
        except (httpx.HTTPError, ValueError, KeyError):
            pass  # Skip if unavailable

    return quotes


@router.get("/top-movers", response_model=list[MarketQuote])
async def get_top_movers(
    source: Source | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    coingecko: CoinGeckoProvider = Depends(get_coingecko),
) -> list[MarketQuote]:
    """Get top movers based on 24h change.

    Note: Currently returns available quotes sorted by change percentage.
    Full implementation requires historical data and caching.

    Args:
        source: Filter by market type (stock, crypto, polymarket).
        limit: Maximum results to return.

    Returns:
        List of quotes sorted by 24h change (descending).
    """
    quotes: list[MarketQuote] = []

    # For now, just fetch crypto as they have 24h change data
    if source is None or source == Source.CRYPTO:
        for symbol in DEFAULT_CRYPTO:
            try:
                quote = await coingecko.get_quote(symbol)
                quotes.append(quote)
            except (httpx.HTTPError, ValueError, KeyError):
                pass  # Skip unavailable

    # Sort by 24h change if available
    def get_change(q: MarketQuote) -> float:
        if q.metadata and "change_24h" in q.metadata:
            return abs(q.metadata["change_24h"] or 0)
        return 0

    quotes.sort(key=get_change, reverse=True)
    return quotes[:limit]


@router.get("/trends")
async def get_trends() -> dict:
    """Get market trends and sentiment summary.

    Note: Placeholder for trend analysis. Full implementation
    requires historical data aggregation and analysis.

    Returns:
        Trend summary with market sentiment indicators.
    """
    return {
        "status": "placeholder",
        "message": "Trend analysis requires historical data aggregation",
        "indicators": {
            "crypto_sentiment": "neutral",
            "stock_sentiment": "neutral",
            "prediction_markets": "active",
        },
    }
