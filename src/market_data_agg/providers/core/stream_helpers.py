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
    stop_event: asyncio.Event | None = None,
) -> AsyncIterator[MarketQuote]:
    """Poll at interval, fetch quotes via fetch_quotes(symbols), yield with optional dedup.

    Uses stop_event when provided (per-stream, safe for concurrent clients). When
    stop_event is None, uses provider.streaming so one client can stop the loop
    (legacy; prefer passing stop_event from the WebSocket handler).

    Args:
        provider: Object implementing PollingStreamable (streaming property).
        symbols: List of symbols to poll.
        poll_interval_seconds: Seconds to sleep between poll rounds.
        fetch_quotes: Async callable(symbols) -> list[MarketQuote].
        dedup_by_value: If True, skip yielding when value unchanged for symbol.
        stop_event: When set, the loop exits. Use one per stream to avoid stopping other clients.
    """
    if not symbols:
        return
    use_stop_event = stop_event is not None
    if not use_stop_event:
        provider.streaming = True
    last_values: dict[str, float] = {}
    try:
        while (stop_event is not None and not stop_event.is_set()) or (
            stop_event is None and provider.streaming
        ):
            quotes = await fetch_quotes(symbols)
            for q in quotes:
                if dedup_by_value and last_values.get(q.symbol) == q.value:
                    continue
                if dedup_by_value:
                    last_values[q.symbol] = q.value
                yield q
            await asyncio.sleep(poll_interval_seconds)
    finally:
        if not use_stop_event:
            provider.streaming = False
