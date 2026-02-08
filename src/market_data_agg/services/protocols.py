"""Protocols for service-layer stream sources."""
import asyncio
from collections.abc import AsyncIterator
from typing import Protocol

from market_data_agg.schemas import MarketQuote


class QuoteStreamable(Protocol):
    """Protocol for objects that can stream MarketQuotes (e.g. a provider)."""

    async def stream(
        self,
        symbol_list: list[str],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[MarketQuote]:
        """Stream quotes for the given symbols until stop_event is set."""
        ...
