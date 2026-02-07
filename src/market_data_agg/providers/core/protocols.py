"""Protocols for market data providers."""
from typing import Protocol

from market_data_agg.schemas import MarketQuote


class PollingStreamable(Protocol):
    """Protocol for providers that use stream_by_polling.

    Must expose a mutable streaming flag so the polling loop can be stopped
    when the client disconnects or close() is called.
    """

    @property
    def streaming(self) -> bool: ...

    @streaming.setter
    def streaming(self, value: bool) -> None:
        self._streaming = value


class ListMarketsProvider(Protocol):
    """Protocol for providers that support listing available markets.

    Extends MarketProviderABC with list_markets (e.g. prediction markets).
    """

    async def list_markets(
        self,
        active: bool = True,
        limit: int = 100,
        tag_id: str | None = None,
    ) -> list[MarketQuote]:
        """List available markets."""
        ...
