"""Protocols for market data services."""
from collections.abc import AsyncIterator
from typing import Protocol

from market_data_agg.schemas import MarketQuote


class QuoteStreamable(Protocol):
    """Protocol for services that can stream MarketQuotes over WebSocket.

    Used by handle_websocket_stream for type-safe streaming.
    """

    async def stream(self, symbol_list: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream real-time quotes for the given symbols."""
