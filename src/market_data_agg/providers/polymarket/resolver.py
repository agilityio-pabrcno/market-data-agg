"""Symbol resolution for Polymarket (slug or condition ID -> market data)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from market_data_agg.providers.polymarket.cache import PolymarketMarketCache


class PolymarketSymbolResolver:
    """Resolves Polymarket symbols (slug or condition ID) to market data.

    Uses Gamma API and a cache to avoid redundant fetches.
    """

    def __init__(
        self,
        gamma_client: httpx.AsyncClient,
        cache: PolymarketMarketCache,
    ) -> None:
        """Initialize resolver.

        Args:
            gamma_client: Async HTTP client configured for Gamma API base URL.
            cache: Cache instance for storing and retrieving market data.
        """
        self._client = gamma_client
        self._cache = cache

    async def resolve(self, symbol: str) -> dict[str, Any]:
        """Resolve symbol to market data.

        Tries cache first, then fetches by slug or condition ID as appropriate.

        Args:
            symbol: Market slug (e.g. "will-bitcoin-reach-100k") or condition ID (hex).

        Returns:
            Market data dict from Gamma API.

        Raises:
            ValueError: If market not found.
        """
        cached = self._cache.get(symbol)
        if cached is not None:
            return cached

        if symbol.startswith("0x"):
            return await self._fetch_by_condition_id(symbol)
        return await self._fetch_by_slug(symbol)

    async def _fetch_by_slug(self, slug: str) -> dict[str, Any]:
        """Fetch market by slug."""
        response = await self._client.get(
            "/markets",
            params={"slug": slug, "limit": 1},
        )
        response.raise_for_status()
        markets = response.json()

        if not markets:
            raise ValueError(f"Market with slug '{slug}' not found")

        market = markets[0]
        slug_key = market.get("slug", slug)
        self._cache.set(slug_key, market)
        return market

    async def _fetch_by_condition_id(self, condition_id: str) -> dict[str, Any]:
        """Fetch market by condition ID."""
        response = await self._client.get(
            "/markets",
            params={"condition_id": condition_id, "limit": 1},
        )
        response.raise_for_status()
        markets = response.json()

        if not markets:
            raise ValueError(f"Market with condition_id '{condition_id}' not found")

        market = markets[0]
        slug = market.get("slug", condition_id)
        self._cache.set(slug, market)
        return market
