"""Markets service: single entry point for stocks, crypto, and predictions.

Holds raw providers; all methods delegate directly to the appropriate provider.
"""
import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from fastapi import HTTPException, WebSocket

from market_data_agg.db import Source
from market_data_agg.providers.core import MarketProviderABC
from market_data_agg.providers.core.protocols import ListMarketsProvider
from market_data_agg.schemas import MarketQuote
from market_data_agg.services.utils import (handle_websocket_stream,
                                            parse_symbols_param)


def _change_key(q: MarketQuote) -> float:
    """Absolute 24h change for sorting; 0 if missing."""
    v = q.metadata.get("change_24h") if q.metadata else None
    return abs(v) if v is not None else 0.0


async def _gather_overview(providers: tuple[MarketProviderABC, ...]) -> list[MarketQuote]:
    """Call get_overview_quotes on each provider; return flattened quotes, skipping failures."""
    results = await asyncio.gather(
        *(p.get_overview_quotes() for p in providers),
        return_exceptions=True,
    )
    quotes: list[MarketQuote] = []
    for result in results:
        if not isinstance(result, Exception):
            quotes.extend(result)
    return quotes


class MarketsService:
    """Single service for stocks, crypto, and predictions. Holds raw providers."""

    def __init__(
        self,
        stocks_provider: MarketProviderABC,
        crypto_provider: MarketProviderABC,
        prediction_provider: MarketProviderABC,
    ) -> None:
        self._stocks = stocks_provider
        self._crypto = crypto_provider
        self._prediction = prediction_provider
        self._all_providers = (self._stocks, self._crypto, self._prediction)
        self._all_names = ("stocks", "crypto", "predictions")
        self._by_source = {
            Source.STOCK: self._stocks,
            Source.CRYPTO: self._crypto,
            Source.PREDICTIONS: self._prediction,
        }

    async def close(self) -> None:
        """Close all providers. Call from app lifespan shutdown."""
        for p in self._all_providers:
            try:
                await p.close()
            except Exception:  # pylint: disable=broad-except
                pass  # TODO: log when logging is added


    # ---- Stocks ----
    async def get_stock_quote(self, symbol: str) -> MarketQuote:
        return await self._stocks.get_quote(symbol)

    async def get_stocks_overview(self) -> list[MarketQuote]:
        return await self._stocks.get_overview_quotes()

    async def get_stock_history(self, symbol: str, days: int) -> list[MarketQuote]:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        return await self._stocks.get_history(symbol, start, end)

    async def refresh_stocks(self) -> None:
        await self._stocks.refresh()

    async def stream_stocks(
        self,
        symbol_list: list[str],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[MarketQuote]:
        async for quote in self._stocks.stream(symbol_list, stop_event=stop_event):
            yield quote

    async def handle_stocks_websocket(
        self, websocket: WebSocket, symbols_required_message: str
    ) -> None:
        symbol_list = parse_symbols_param(websocket.query_params)
        await handle_websocket_stream(
            websocket,
            lambda s, e: self.stream_stocks(s, stop_event=e),
            symbol_list,
            symbols_required_message,
        )

    # ---- Crypto ----
    async def get_crypto_quote(self, symbol: str) -> MarketQuote:
        return await self._crypto.get_quote(symbol)

    async def get_crypto_overview(self) -> list[MarketQuote]:
        return await self._crypto.get_overview_quotes()

    async def get_crypto_history(self, symbol: str, days: int) -> list[MarketQuote]:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        return await self._crypto.get_history(symbol, start, end)

    async def refresh_crypto(self) -> None:
        await self._crypto.refresh()

    async def stream_crypto(
        self,
        symbol_list: list[str],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[MarketQuote]:
        async for quote in self._crypto.stream(symbol_list, stop_event=stop_event):
            yield quote

    async def handle_crypto_websocket(
        self, websocket: WebSocket, symbols_required_message: str
    ) -> None:
        symbol_list = parse_symbols_param(websocket.query_params)
        await handle_websocket_stream(
            websocket,
            lambda s, e: self.stream_crypto(s, stop_event=e),
            symbol_list,
            symbols_required_message,
        )

    # ---- Predictions ----
    async def get_prediction_quote(self, symbol: str) -> MarketQuote:
        return await self._prediction.get_quote(symbol)

    async def get_prediction_overview(self) -> list[MarketQuote]:
        return await self._prediction.get_overview_quotes()

    async def list_prediction_markets(
        self,
        active: bool = True,
        limit: int = 100,
        tag_id: str | None = None,
    ) -> list[MarketQuote]:
        if not isinstance(self._prediction, ListMarketsProvider):
            raise HTTPException(501, detail="Provider does not support list_markets")
        return await self._prediction.list_markets(
            active=active, limit=limit, tag_id=tag_id
        )

    async def refresh_predictions(self) -> None:
        await self._prediction.refresh()

    async def stream_predictions(
        self,
        symbol_list: list[str],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[MarketQuote]:
        async for quote in self._prediction.stream(
            symbol_list, stop_event=stop_event
        ):
            yield quote

    async def handle_predictions_websocket(
        self, websocket: WebSocket, symbols_required_message: str
    ) -> None:
        symbol_list = parse_symbols_param(websocket.query_params)
        await handle_websocket_stream(
            websocket,
            lambda s, e: self.stream_predictions(s, stop_event=e),
            symbol_list,
            symbols_required_message,
        )

    # ---- Aggregated ----
    async def get_overview(self) -> list[MarketQuote]:
        return await _gather_overview(self._all_providers)

    async def get_predictions_overview(self) -> list[MarketQuote]:
        """Alias for get_prediction_overview (e.g. /predictions/overview)."""
        return await self.get_prediction_overview()

    async def get_top_movers(
        self,
        source: Source | None = None,
        limit: int = 10,
    ) -> list[MarketQuote]:
        if source is not None:
            provider = self._by_source.get(source)
            quotes = await provider.get_overview_quotes() if provider else []
        else:
            quotes = await _gather_overview(self._all_providers)
        quotes.sort(key=_change_key, reverse=True)
        return quotes[:limit]
        return quotes[:limit]
