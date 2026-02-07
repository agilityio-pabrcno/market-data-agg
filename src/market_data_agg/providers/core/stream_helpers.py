"""Shared polling-based stream helper for market data providers."""
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from market_data_agg.providers.core.protocols import PollingStreamable
from market_data_agg.schemas import MarketQuote


async def stream_by_polling(
    provider: PollingStreamable,
    symbols: list[str],
    poll_interval_seconds: float,
    fetch_quotes: Callable[[list[str]], Awaitable[list[MarketQuote]]],
    *,
    dedup_by_value: bool = True,
) -> AsyncIterator[MarketQuote]:
    """Poll at interval, fetch quotes via fetch_quotes(symbols), yield with optional dedup.

    Sets provider.streaming = True for the duration and False in finally.
    If dedup_by_value is True, yields only when quote.value changed for that symbol.

    Args:
        provider: Object implementing PollingStreamable (streaming property).
        symbols: List of symbols to poll.
        poll_interval_seconds: Seconds to sleep between poll rounds.
        fetch_quotes: Async callable(symbols) -> list[MarketQuote].
        dedup_by_value: If True, skip yielding when value unchanged for symbol.
    """
    if not symbols:
        return
    provider.streaming = True
    last_values: dict[str, float] = {}
    try:
        while provider.streaming:
            quotes = await fetch_quotes(symbols)
            for q in quotes:
                if dedup_by_value and last_values.get(q.symbol) == q.value:
                    continue
                if dedup_by_value:
                    last_values[q.symbol] = q.value
                yield q
            await asyncio.sleep(poll_interval_seconds)
    finally:
        provider.streaming = False
