"""Yahoo Finance market data provider for stocks."""
import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

import yfinance as yf

from market_data_agg.db import Source
from market_data_agg.providers.base import MarketProvider
from market_data_agg.schemas import MarketQuote, StreamMessage


class YFinanceProvider(MarketProvider):
    """Market data provider for stocks via Yahoo Finance.

    Uses yfinance library for stock quotes and historical data.
    No API key required. Implements polling-based streaming since
    yfinance doesn't provide WebSocket support.
    """

    def __init__(self, poll_interval: float = 15.0) -> None:
        """Initialize the YFinance provider.

        Args:
            poll_interval: Interval in seconds for polling-based streaming.
        """
        self._poll_interval = poll_interval
        self._streaming = False

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize a stock symbol (uppercase)."""
        return symbol.upper()

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current quote for a stock symbol.

        Args:
            symbol: Stock ticker (e.g., "AAPL", "MSFT").

        Returns:
            MarketQuote with the current price.
        """
        symbol = self._normalize_symbol(symbol)

        # Run yfinance in a thread since it's synchronous
        def _fetch_quote() -> MarketQuote:
            ticker = yf.Ticker(symbol)
           
            # Try fast_info first (lighter weight)
            try:
                info = ticker.fast_info
                price = info.get("lastPrice") or info.get("regularMarketPrice")
                volume = info.get("lastVolume")
               
                if price is None:
                    # Fallback to full info if fast_info doesn't have price
                    full_info = ticker.info
                    price = full_info.get("currentPrice") or full_info.get("regularMarketPrice")
                    volume = full_info.get("volume")
               
                if price is None:
                    raise ValueError(f"Stock '{symbol}' not found or has no price data")
               
                return MarketQuote(
                    source=Source.STOCK,
                    symbol=symbol,
                    value=float(price),
                    volume=float(volume) if volume else None,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "provider": "yfinance",
                    },
                )
            except Exception as e:
                raise ValueError(f"Failed to fetch quote for '{symbol}': {e}") from e

        return await asyncio.to_thread(_fetch_quote)

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
        symbol = self._normalize_symbol(symbol)

        # Run yfinance in a thread since it's synchronous
        def _fetch_history() -> list[MarketQuote]:
            ticker = yf.Ticker(symbol)
            
            try:
                # Fetch daily history
                df = ticker.history(start=start, end=end, interval="1d")
                
                if df.empty:
                    return []
                
                quotes: list[MarketQuote] = []
                for timestamp, row in df.iterrows():
                    # Skip rows with NaN values
                    if row.isna().any():
                        continue
                    
                    quotes.append(
                        MarketQuote(
                            source=Source.STOCK,
                            symbol=symbol,
                            value=float(row["Close"]),
                            volume=float(row["Volume"]) if row["Volume"] else None,
                            timestamp=timestamp.to_pydatetime(),
                            metadata={
                                "open": float(row["Open"]),
                                "high": float(row["High"]),
                                "low": float(row["Low"]),
                                "provider": "yfinance",
                            },
                        )
                    )
                
                return quotes
            except Exception as e:
                raise ValueError(f"Failed to fetch history for '{symbol}': {e}") from e

        return await asyncio.to_thread(_fetch_history)

    async def stream(self, symbols: list[str]) -> AsyncIterator[StreamMessage]:
        """Stream real-time price updates via polling.

        Yahoo Finance doesn't provide WebSocket support, so this
        implementation polls the REST API at regular intervals.

        Args:
            symbols: List of stock tickers to stream (e.g., ["AAPL", "MSFT"]).

        Yields:
            StreamMessage objects with price updates.
        """
        self._streaming = True
        normalized_symbols = [self._normalize_symbol(s) for s in symbols]

        # Track last prices to only emit on change
        last_prices: dict[str, float] = {}

        try:
            while self._streaming:
                for symbol in normalized_symbols:
                    try:
                        quote = await self.get_quote(symbol)
                        price = quote.value

                        # Only emit if price changed
                        if symbol in last_prices and last_prices[symbol] == price:
                            continue

                        last_prices[symbol] = price

                        yield StreamMessage(
                            source=Source.STOCK,
                            symbol=symbol,
                            price=price,
                            timestamp=quote.timestamp,
                        )
                    except (ValueError, KeyError):
                        # Skip symbols that fail to fetch
                        continue

                await asyncio.sleep(self._poll_interval)
        finally:
            self._streaming = False

    async def refresh(self) -> None:
        """Force refresh - no-op for yfinance provider."""

    async def close(self) -> None:
        """Clean up resources."""
        self._streaming = False
