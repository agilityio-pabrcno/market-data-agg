"""Abstract base class for market data providers."""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime

from market_data_agg.schemas import MarketQuote


class MarketProviderABC(ABC):
    """Base interface for all market data providers.

    Each market data provider implements this interface
    to provide a unified way to fetch quotes, historical data, and real-time streams.

    Subclasses must call super().__init__() and must not set _streaming directly;
    the streaming property is used by stream_by_polling to stop when close() is called.
    """

    def __init__(self) -> None:
        """Initialize provider. Subclasses may override and should call super().__init__()."""
        self._streaming = False

    @property
    def streaming(self) -> bool:
        """Flag used by stream_by_polling to control the polling loop."""
        return getattr(self, "_streaming", False)

    @streaming.setter
    def streaming(self, value: bool) -> None:
        self._streaming = value

    @abstractmethod
    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current quote for a symbol.

        Args:
            symbol: The asset symbol (e.g., "AAPL", "BTC", "event-slug").

        Returns:
            A MarketQuote with the current price/value.
        """

    @abstractmethod
    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Fetch the main/top quotes for overview (e.g. top stocks, top crypto, active markets).

        Each implementation defines what "overview" means and uses a single batch
        request or asyncio.gather for multiple symbols; no per-symbol loops in callers.

        Returns:
            List of MarketQuotes for the provider's default overview set.
        """

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        """Fetch historical quotes for a symbol within a time range.

        Default implementation raises NotImplementedError. Override in providers
        that support historical data (e.g. stocks, crypto).

        Args:
            symbol: The asset symbol.
            start: Start of the time range (inclusive).
            end: End of the time range (inclusive).

        Returns:
            A list of MarketQuotes ordered by timestamp.
        """
        raise NotImplementedError("Historical data is not supported by this provider")

    @abstractmethod
    async def stream(self, symbols: list[str]) -> AsyncIterator[MarketQuote]:
        """Subscribe to real-time updates for the given symbols.

        This is an async generator that yields MarketQuote objects
        as updates arrive from the provider.

        Args:
            symbols: List of symbols to subscribe to.

        Yields:
            MarketQuote objects with real-time price/value updates.
        """
        # This yield is needed to make this an async generator in the ABC
        yield  # type: ignore[misc]

    @abstractmethod
    async def refresh(self) -> None:
        """Force refresh or reconnect.

        Use this to re-establish connections, clear caches, or
        re-authenticate with the provider.
        """

    async def close(self) -> None:
        """Clean up resources (connections, clients).

        Override in subclasses if cleanup is needed.
        """

    async def __aenter__(self) -> "MarketProviderABC":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Async context manager exit - calls close()."""
        await self.close()
