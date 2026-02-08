"""WebSocket stream handling: parse symbols and stream MarketQuotes from a service."""
import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from market_data_agg.schemas import MarketQuote
from market_data_agg.services.protocols import QuoteStreamable

logger = logging.getLogger(__name__)

StreamSource = QuoteStreamable | Callable[
    [list[str], asyncio.Event], AsyncIterator[MarketQuote]
]


def parse_symbols_param(
    query_params: Any,
    normalizer: Callable[[str], str] | None = None,
) -> list[str]:
    """Parse comma-separated 'symbols' query param into a list, optionally normalizing each."""
    raw = (query_params.get("symbols") or "").strip()
    parts = [s.strip() for s in raw.split(",") if s.strip()]
    if normalizer is None:
        return parts
    return [normalizer(s) for s in parts]


async def handle_websocket_stream(
    websocket: WebSocket,
    stream_source: StreamSource,
    symbol_list: list[str],
    symbols_required_message: str,
) -> None:
    """Accept WebSocket, validate symbols, then stream MarketQuotes.

    stream_source: either a QuoteStreamable (has .stream) or a callable
    (symbol_list, stop_event) -> AsyncIterator[MarketQuote].
    Uses a per-connection stop_event so one client disconnect does not stop
    other clients (safe with singleton providers).
    """
    await websocket.accept()
    if not symbol_list:
        await websocket.close(code=4000, reason=symbols_required_message)
        return
    stop_event: asyncio.Event = asyncio.Event()
    try:
        if callable(stream_source):
            stream = stream_source(symbol_list, stop_event)
        else:
            stream = stream_source.stream(symbol_list, stop_event=stop_event)
        async for quote in stream:
            if isinstance(quote, MarketQuote):
                await websocket.send_json(quote.model_dump(mode="json"))
    except WebSocketDisconnect:
        logger.debug("Stream client disconnected")
    except Exception as exc:
        logger.exception("Stream error: %s", exc)
        try:
            await websocket.close(code=1011, reason="Stream error")
        except Exception:
            pass
    finally:
        stop_event.set()
