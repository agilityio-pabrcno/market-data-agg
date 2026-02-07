"""WebSocket stream handling: parse symbols and stream MarketQuotes from a service."""
import logging
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from market_data_agg.schemas import MarketQuote
from market_data_agg.services.protocols import QuoteStreamable

logger = logging.getLogger(__name__)


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
    service: QuoteStreamable,
    symbol_list: list[str],
    symbols_required_message: str,
) -> None:
    """Accept WebSocket, validate symbols, then stream MarketQuotes from the service.

    Service must implement stream(symbol_list: list[str]) -> AsyncIterator[MarketQuote].
    """
    await websocket.accept()
    if not symbol_list:
        await websocket.close(code=4000, reason=symbols_required_message)
        return
    try:
        async for quote in service.stream(symbol_list):
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
