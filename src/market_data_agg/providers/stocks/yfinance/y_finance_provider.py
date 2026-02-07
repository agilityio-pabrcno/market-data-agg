"""Yahoo Finance market data provider for stocks."""
import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

import yfinance as yf

from market_data_agg.db import Source
from market_data_agg.providers.core import MarketProviderABC
from market_data_agg.providers.stocks.yfinance.models import YFinanceBarMetadata
from market_data_agg.schemas import MarketQuote


class YFinanceProvider(MarketProviderABC):
    """Market data provider for stocks via Yahoo Finance.

    Uses yfinance library for stock quotes and historical data.
    No API key required. Implements polling-based streaming since
    yfinance doesn't provide WebSocket support.
    """

    OVERVIEW_SYMBOLS = ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA")

    def __init__(self, poll_interval: float = 15.0) -> None:
        """Initialize the YFinance provider.

        Args:
            poll_interval: Interval in seconds for polling-based streaming.
        """
        self._poll_interval = poll_interval
        self._streaming = False

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize a stock symbol (uppercase)."""
        return symbol.upper()

    @staticmethod
    def _quote(
        symbol: str,
        value: float,
        volume: float | None,
        *,
        metadata: dict | None = None,
    ) -> MarketQuote:
        """Build a MarketQuote from price/volume."""
        return MarketQuote(
            source=Source.STOCK,
            symbol=symbol,
            value=value,
            volume=volume,
            timestamp=datetime.utcnow(),
            metadata=metadata or {"provider": "yfinance"},
        )

    def _fetch_quote_sync(self, symbol: str) -> MarketQuote:
        """Fetch a single quote synchronously (run in thread)."""
        ticker = yf.Ticker(symbol)
        try:
            info = getattr(ticker, "fast_info", None)
            price = None
            volume = None
            if info is not None:
                price = info.get("lastPrice") or info.get("regularMarketPrice")
                volume = info.get("lastVolume")
            if price is None:
                full = ticker.info
                price = full.get("currentPrice") or full.get("regularMarketPrice")
                volume = volume if volume is not None else full.get("volume")
            if price is None:
                raise ValueError(f"Stock '{symbol}' not found or has no price data")
            return self._quote(
                symbol,
                float(price),
                float(volume) if volume is not None else None,
            )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to fetch quote for '{symbol}': {e}") from e

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current quote for a stock symbol.

        Args:
            symbol: Stock ticker (e.g., "AAPL", "MSFT").

        Returns:
            MarketQuote with the current price.
        """
        sym = self._normalize_symbol(symbol)
        return await asyncio.to_thread(self._fetch_quote_sync, sym)

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Fetch quotes for the main overview symbols in parallel."""
        results = await asyncio.gather(
            *[self.get_quote(s) for s in self.OVERVIEW_SYMBOLS],
            return_exceptions=True,
        )
        return [q for q in results if isinstance(q, MarketQuote)]

    @staticmethod
    def _quote_from_row(symbol: str, timestamp: datetime, row: "object") -> MarketQuote:
        """Build a MarketQuote from a history DataFrame row."""
        vol = row["Volume"]
        bar = YFinanceBarMetadata(
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
        )
        return MarketQuote(
            source=Source.STOCK,
            symbol=symbol,
            value=float(row["Close"]),
            volume=float(vol) if vol else None,
            timestamp=timestamp,
            metadata=bar.model_dump(),
        )

    def _fetch_history_sync(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        """Fetch history synchronously (run in thread)."""
        ticker = yf.Ticker(symbol)
        try:
            df = ticker.history(start=start, end=end, interval="1d")
            if df.empty:
                return []
            return [
                self._quote_from_row(symbol, ts.to_pydatetime(), row)
                for ts, row in df.iterrows()
                if not row.isna().any()
            ]
        except Exception as e:
            raise ValueError(f"Failed to fetch history for '{symbol}': {e}") from e

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        """Fetch historical bar data for a stock.

        Args:
            symbol: Stock ticker.
            start: Start of time range.
            end: End of time range.

        Returns:
            List of MarketQuotes (daily bars) ordered by timestamp.
        """
        sym = self._normalize_symbol(symbol)
        return await asyncio.to_thread(self._fetch_history_sync, sym, start, end)

    async def stream(self, symbols: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream real-time price updates via polling.

        Yahoo Finance doesn't provide WebSocket support, so this
        implementation polls the REST API at regular intervals.

        Args:
            symbols: List of stock tickers to stream (e.g., ["AAPL", "MSFT"]).

        Yields:
            MarketQuote objects with price updates.
        """
        self._streaming = True
        normalized = [self._normalize_symbol(s) for s in symbols]
        last_prices: dict[str, float] = {}

        try:
            while self._streaming:
                results = await asyncio.gather(
                    *[self.get_quote(s) for s in normalized],
                    return_exceptions=True,
                )
                for q in results:
                    if not isinstance(q, MarketQuote):
                        continue
                    if last_prices.get(q.symbol) == q.value:
                        continue
                    last_prices[q.symbol] = q.value
                    yield q

                await asyncio.sleep(self._poll_interval)
        finally:
            self._streaming = False

    async def refresh(self) -> None:
        """Force refresh - no-op for yfinance provider."""

    async def close(self) -> None:
        """Clean up resources."""
        self._streaming = False
