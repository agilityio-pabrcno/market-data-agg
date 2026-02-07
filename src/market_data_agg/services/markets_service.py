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


async def gather_overview_quotes(
    providers: tuple[MarketProviderABC, ...],
    provider_names: tuple[str, ...],
    *,
    log_context: str = "Markets",
) -> list[MarketQuote]:
    """Gather overview quotes from all providers; failed providers are omitted.

    Args:
        providers: Providers to query.
        provider_names: Names for logging (order must match providers).
        log_context: Prefix for log messages when a provider fails.

    Returns:
        Combined list of quotes; failures are logged and skipped.
    """
    results = await asyncio.gather(
        *(p.get_overview_quotes() for p in providers),
        return_exceptions=True,
    )
    quotes: list[MarketQuote] = []
    for name, result in zip(provider_names, results):
        if isinstance(result, Exception):
            logger.warning("%s: %s provider failed: %s", log_context, name, result)
            continue
        quotes.extend(result)
    return quotes


class MarketsService:
    """Aggregates overview and top-movers from stocks, crypto, and prediction providers."""

    # TODO: add logger (e.g. self._logger = logging.getLogger(__name__)) for method-level logging

    def __init__(
        self,
        stocks_provider: MarketProviderABC,
        crypto_provider: MarketProviderABC,
        prediction_providers: list[tuple[str, PredictionsProviderABC]],
    ) -> None:
        self._stocks = stocks_provider
        self._crypto = crypto_provider
        self._prediction_providers = prediction_providers
        self._all_providers = (
            stocks_provider,
            crypto_provider,
            *(p for _, p in prediction_providers),
        )
        self._all_names = (
            "stocks",
            "crypto",
            *(name for name, _ in prediction_providers),
        )
        self._by_source = {
            Source.STOCK: stocks_provider,
            Source.CRYPTO: crypto_provider,
        }

    async def get_overview(self) -> list[MarketQuote]:
        """Overview quotes from all providers; failed providers are omitted."""
        # TODO: add logger (e.g. debug on entry, info with quote count on success)
        return await gather_overview_quotes(
            self._all_providers,
            self._all_names,
            log_context="Markets overview",
        )

    async def get_predictions_overview(self) -> list[MarketQuote]:
        """Overview quotes from prediction providers only (e.g. Polymarket, Kalshi)."""
        # TODO: add logger (e.g. debug on entry, info with count when providers present)
        if not self._prediction_providers:
            return []
        providers = tuple(p for _, p in self._prediction_providers)
        names = tuple(n for n, _ in self._prediction_providers)
        return await gather_overview_quotes(
            providers, names, log_context="Predictions overview"
        )

    async def get_top_movers(
        self,
        source: Source | None = None,
        limit: int = 10,
    ) -> list[MarketQuote]:
        """Top movers by absolute 24h change; optional filter by source."""
        # TODO: add logger (e.g. debug with source/limit, info with result count)
        if source is None:
            quotes = await gather_overview_quotes(
                self._all_providers,
                self._all_names,
                log_context="Top movers",
            )
        elif source == Source.PREDICTIONS:
            # Aggregate all prediction providers
            all_pred_providers = tuple(p for _, p in self._prediction_providers)
            all_pred_names = tuple(n for n, _ in self._prediction_providers)
            quotes = await gather_overview_quotes(
                all_pred_providers,
                all_pred_names,
                log_context="Top movers",
            )
        else:
            provider = self._by_source.get(source, self._stocks)
            quotes = await provider.get_overview_quotes()
        quotes.sort(key=_change_24h, reverse=True)
        return quotes[:limit]
