"""Polymarket data provider for prediction markets."""
from collections.abc import AsyncIterator
from typing import Any

import httpx

from market_data_agg.providers.core.stream_helpers import stream_by_polling
from market_data_agg.providers.predictions.polymarket.polymarket_dto import (
    PolymarketEventDTO, PolymarketMarketDTO)
from market_data_agg.providers.predictions.predictions_provider_abc import \
    PredictionsProviderABC
from market_data_agg.schemas import MarketQuote


class PolymarketProvider(PredictionsProviderABC):
    """Polymarket data provider for prediction markets.

    Uses the Gamma API for market metadata. Stream polls get_quote every
    poll_interval seconds for each requested symbol.
    """

    GAMMA_API_URL = "https://gamma-api.polymarket.com"

    def __init__(self, poll_interval_seconds: float = 60.0) -> None:
        """Initialize the Polymarket provider.

        Args:
            poll_interval_seconds: Seconds between refresh when streaming (default 60).
        """
        super().__init__()
        self._poll_interval_seconds = poll_interval_seconds
        self._gamma_client = httpx.AsyncClient(base_url=self.GAMMA_API_URL)

    async def _fetch_market(self, symbol: str) -> PolymarketMarketDTO:
        """Fetch a single market by slug from the Gamma API.

        Symbol must be the market slug (e.g. "will-bitcoin-hit-100k"), as in
        the Polymarket URL path. Condition IDs (0x...) are not supported.
        """
        response = await self._gamma_client.get(
            "/markets",
            params={"slug": symbol, "limit": 1},
        )
        response.raise_for_status()
        markets = response.json()
        if not markets:
            raise ValueError(f"Market not found: {symbol}")
        return PolymarketMarketDTO.model_validate(markets[0])

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current probability for a prediction market.

        Args:
            symbol: Market slug (e.g. from the Polymarket URL).

        Returns:
            MarketQuote with symbol=question, value=max outcome probability, volume=total USD.
        """
        market_dto = await self._fetch_market(symbol)
        return market_dto.to_market_quote()

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Fetch active prediction markets for overview."""
        return await self.list_markets(active=True, limit=5)

    async def stream(self, symbols: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream quotes by polling get_quote for each symbol every poll_interval seconds.

        Args:
            symbols: List of market slugs.

        Yields:
            MarketQuote from get_quote for each symbol, every poll_interval seconds.
        """
        async def fetch_all(syms: list[str]) -> list[MarketQuote]:
            return [await self.get_quote(s) for s in syms]

        async for quote in stream_by_polling(
            self,
            symbols,
            self._poll_interval_seconds,
            fetch_all,
            dedup_by_value=False,
        ):
            yield quote

    async def list_markets(
        self,
        active: bool = True,
        limit: int = 100,
        tag_id: str | None = None,
    ) -> list[MarketQuote]:
        """List available prediction markets.

        Args:
            active: Filter for active markets only.
            limit: Maximum number of markets to return.
            tag_id: Optional tag ID to filter by category.

        Returns:
            List of MarketQuotes for available markets.
        """
        params: dict[str, Any] = {
            "active": str(active).lower(),
            "closed": "false",
            "limit": limit,
        }
        if tag_id:
            params["tag_id"] = tag_id

        response = await self._gamma_client.get("/events", params=params)
        response.raise_for_status()
        events_data = response.json()

        quotes: list[MarketQuote] = []
        for event_data in events_data:
            event_dto = PolymarketEventDTO.model_validate(event_data)
            for market_dto in event_dto.markets:
                quotes.append(market_dto.to_market_quote())

        return quotes

    async def refresh(self) -> None:
        """Stop the current stream loop so the next stream() starts fresh."""
        self.streaming = False

    async def close(self) -> None:
        """Close Gamma HTTP client."""
        self.streaming = False
        await self._gamma_client.aclose()
