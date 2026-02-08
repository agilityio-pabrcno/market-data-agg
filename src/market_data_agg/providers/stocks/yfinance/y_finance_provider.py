"""Yahoo Finance market data provider for stocks."""
import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

import yfinance as yf

from market_data_agg.db import Source
from market_data_agg.providers.core import MarketProviderABC, round2
from market_data_agg.providers.core.stream_helpers import stream_by_polling
from market_data_agg.providers.core.utils import normalize_stock_symbol
from market_data_agg.providers.stocks.yfinance.models import \
    YFinanceBarMetadata
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
        super().__init__()
        self._poll_interval = poll_interval

    def _extract_price_volume(
        self, ticker: yf.Ticker, symbol: str
    ) -> tuple[float, float | None]:
        """Extract price and volume from ticker; raises if price unavailable."""
        info = getattr(ticker, "fast_info", None)
        if info and (price := info.get("lastPrice") or info.get("regularMarketPrice")):
            vol = info.get("lastVolume")
            return float(price), float(vol) if vol is not None else None
        full = ticker.info
        price = full.get("currentPrice") or full.get("regularMarketPrice")
        if price is None:
            raise ValueError(f"Stock '{symbol}' not found or has no price data")
        vol = full.get("volume")
        return float(price), float(vol) if vol is not None else None

    def _fetch_quote_sync(self, symbol: str) -> MarketQuote:
        """Fetch a single quote synchronously (run in thread)."""
        ticker = yf.Ticker(symbol)
        try:
            price, volume = self._extract_price_volume(ticker, symbol)
            return MarketQuote(
                source=Source.STOCK,
                symbol=symbol,
                value=round2(price),
                volume=round2(volume),
                timestamp=datetime.utcnow(),
                metadata={"provider": "yfinance"},
            )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to fetch quote for '{symbol}': {e}") from e

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current quote for a stock symbol."""
        sym = normalize_stock_symbol(symbol)
        return await asyncio.to_thread(self._fetch_quote_sync, sym)

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Fetch quotes for the main overview symbols in parallel."""
        results = await asyncio.gather(
            *[self.get_quote(s) for s in self.OVERVIEW_SYMBOLS],
            return_exceptions=True,
        )
        return [q for q in results if isinstance(q, MarketQuote)]

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        """Fetch historical bar data for a stock."""
        sym = normalize_stock_symbol(symbol)
        try:
            df = await asyncio.to_thread(
                lambda: yf.Ticker(sym).history(start=start, end=end, interval="1d")
            )
            if df.empty:
                return []
            return [
                MarketQuote(
                    source=Source.STOCK,
                    symbol=sym,
                    value=round2(float(row["Close"])),
                    volume=round2(float(row["Volume"])) if row["Volume"] else None,
                    timestamp=ts.to_pydatetime(),
                    metadata=YFinanceBarMetadata(
                        open=round2(float(row["Open"])),
                        high=round2(float(row["High"])),
                        low=round2(float(row["Low"])),
                    ).model_dump(),
                )
                for ts, row in df.iterrows()
                if not row.isna().any()
            ]
        except Exception as e:
            raise ValueError(f"Failed to fetch history for '{sym}': {e}") from e

    async def stream(
        self,
        symbols: list[str],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[MarketQuote]:
        """Stream real-time price updates via polling.

        Yahoo Finance doesn't provide WebSocket support, so this
        implementation polls the REST API at regular intervals.

        Args:
            symbols: List of stock tickers to stream (e.g., ["AAPL", "MSFT"]).
            stop_event: When set, the polling loop exits (per-stream; safe for concurrent clients).

        Yields:
            MarketQuote objects with price updates.
        """
        normalized = [normalize_stock_symbol(s) for s in symbols]

        async for quote in stream_by_polling(
            self,
            normalized,
            self._poll_interval,
            self._fetch_stream_batch,
            dedup_by_value=True,
            stop_event=stop_event,
        ):
            yield quote

    async def _fetch_stream_batch(self, syms: list[str]) -> list[MarketQuote]:
        """Fetch quotes for the given symbols (used by stream)."""
        results = await asyncio.gather(
            *[self.get_quote(s) for s in syms],
            return_exceptions=True,
        )
        return [q for q in results if isinstance(q, MarketQuote)]

    async def refresh(self) -> None:
        """Force refresh - no-op for yfinance provider."""

    async def close(self) -> None:
        """Clean up resources."""
        self.streaming = False
