"""Markets service: aggregated overview and top-movers across providers."""
import asyncio
import logging

from market_data_agg.db import Source
from market_data_agg.providers import MarketProviderABC, PredictionsProviderABC
from market_data_agg.schemas import MarketQuote

logger = logging.getLogger(__name__)


def _change_24h(q: MarketQuote) -> float:
    """Helper for sorting by absolute 24h change."""
    if q.metadata and "change_24h" in q.metadata:
        val = q.metadata["change_24h"]
        return abs(val) if val is not None else 0.0
    return 0.0


class MarketsService:
    """Aggregates overview and top-movers from stocks, crypto, and predictions providers."""

    def __init__(
        self,
        stocks_provider: MarketProviderABC,
        crypto_provider: MarketProviderABC,
        predictions_provider: PredictionsProviderABC,
    ) -> None:
        self._stocks = stocks_provider
        self._crypto = crypto_provider
        self._predictions = predictions_provider

    async def get_overview(self) -> list[MarketQuote]:
        """Overview quotes from all providers; failed providers are omitted."""
        results = await asyncio.gather(
            self._stocks.get_overview_quotes(),
            self._crypto.get_overview_quotes(),
            self._predictions.get_overview_quotes(),
            return_exceptions=True,
        )
        quotes: list[MarketQuote] = []
        for name, result in zip(("stocks", "crypto", "predictions"), results):
            if isinstance(result, Exception):
                logger.warning("Markets overview: %s provider failed: %s", name, result)
                continue
            quotes.extend(result)
        return quotes

    async def get_top_movers(
        self,
        source: Source | None = None,
        limit: int = 10,
    ) -> list[MarketQuote]:
        """Top movers by absolute 24h change; optional filter by source."""
        if source is None:
            results = await asyncio.gather(
                self._stocks.get_overview_quotes(),
                self._crypto.get_overview_quotes(),
                self._predictions.get_overview_quotes(),
                return_exceptions=True,
            )
            quotes = []
            for name, result in zip(("stocks", "crypto", "predictions"), results):
                if isinstance(result, Exception):
                    logger.warning("Top movers: %s provider failed: %s", name, result)
                    continue
                quotes.extend(result)
        else:
            provider = {
                Source.STOCK: self._stocks,
                Source.CRYPTO: self._crypto,
                Source.PREDICTIONS: self._predictions,
            }.get(source, self._predictions)
            quotes = await provider.get_overview_quotes()
        quotes.sort(key=_change_24h, reverse=True)
        return quotes[:limit]
