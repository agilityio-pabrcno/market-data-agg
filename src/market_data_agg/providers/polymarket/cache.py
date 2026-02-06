"""Cache for Polymarket market data and token-to-market resolution."""
from typing import Any


class PolymarketMarketCache:
    """Cache for Polymarket market metadata and token ID mappings.

    Stores market data keyed by slug, with secondary indexing by condition_id
    and token_id for efficient lookups during WebSocket event handling.
    """

    def __init__(self) -> None:
        """Initialize empty cache."""
        self._by_slug: dict[str, dict[str, Any]] = {}
        self._by_condition_id: dict[str, str] = {}  # condition_id -> slug
        self._token_to_slug_outcome: dict[str, tuple[str, int]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        """Get market by slug or condition ID.

        Args:
            key: Market slug (e.g. "will-bitcoin-reach-100k") or condition ID.

        Returns:
            Market data dict if cached, None otherwise.
        """
        if key in self._by_slug:
            return self._by_slug[key]
        slug = self._by_condition_id.get(key)
        return self._by_slug.get(slug) if slug else None

    def set(self, slug: str, market: dict[str, Any]) -> None:
        """Store market and populate token ID mappings.

        Args:
            slug: Market slug (primary key).
            market: Raw market data from Gamma API.
        """
        self._by_slug[slug] = market

        condition_id = market.get("conditionId")
        if condition_id:
            self._by_condition_id[condition_id] = slug

        token_ids = market.get("clobTokenIds", [])
        for i, token_id in enumerate(token_ids):
            self._token_to_slug_outcome[token_id] = (slug, i)

    def get_slug_for_token(self, token_id: str) -> tuple[str, int] | None:
        """Resolve token ID to (slug, outcome_index).

        Args:
            token_id: CLOB token ID from WebSocket events.

        Returns:
            (slug, outcome_index) if known, None otherwise.
        """
        return self._token_to_slug_outcome.get(token_id)

    def clear(self) -> None:
        """Clear all cached data."""
        self._by_slug.clear()
        self._by_condition_id.clear()
        self._token_to_slug_outcome.clear()
