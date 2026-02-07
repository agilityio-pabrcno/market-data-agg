"""Unified market data service with dependency injection.

MarketService wraps any MarketProviderABC with error mapping and symbol normalization.
Inject different provider + error mapper combinations for stocks, crypto, predictions.
"""
import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta

import httpx
from fastapi import WebSocket

from market_data_agg.providers.core import (MarketProviderABC,
                                            ProviderErrorMapper)
from market_data_agg.providers.core.protocols import ListMarketsProvider
from market_data_agg.schemas import MarketQuote
from market_data_agg.services.utils import (handle_websocket_stream,
                                            parse_symbols_param)

# Exceptions from providers we map to HTTP; all others propagate (e.g. bugs, BaseException).
_PROVIDER_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValueError,
    KeyError,
    TypeError,
    TimeoutError,
    OSError,
    asyncio.TimeoutError,
    httpx.HTTPStatusError,
)


class MarketService:
    """Unified service over a market provider; maps provider errors to HTTP.

    Injected with provider and error mapper so different instances serve
    different domains (stocks, crypto, predictions) with appropriate config.
    """

    def __init__(
        self,
        provider: MarketProviderABC,
        error_mapper: ProviderErrorMapper,
        *,
        symbol_normalizer: Callable[[str], str] | None = None,
    ) -> None:
        """Initialize with provider and error mapping config.

        Args:
            provider: The market data provider (e.g. YFinanceProvider, CoinGeckoProvider).
            error_mapper: Maps provider exceptions to HTTP (resource_name, api_name).
            symbol_normalizer: Optional normalizer for symbols (e.g. str.upper for stocks).
        """
        self._provider = provider
        self._error_mapper = error_mapper
        self._normalize = symbol_normalizer or (lambda s: s)

    def _normalize_symbol(self, symbol: str) -> str:
        return self._normalize(symbol)

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Get current quote. Raises HTTPException on provider errors."""
        norm = self._normalize_symbol(symbol)
        try:
            return await self._provider.get_quote(norm)
        except _PROVIDER_EXCEPTIONS as e:
            self._error_mapper.raise_http(e, symbol=symbol)

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Get overview quotes. Raises HTTPException on provider errors."""
        try:
            return await self._provider.get_overview_quotes()
        except _PROVIDER_EXCEPTIONS as e:
            self._error_mapper.raise_http(e)

    async def get_history(self, symbol: str, days: int) -> list[MarketQuote]:
        """Get historical quotes. Raises HTTPException on provider errors."""
        norm = self._normalize_symbol(symbol)
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        try:
            return await self._provider.get_history(norm, start, end)
        except _PROVIDER_EXCEPTIONS as e:
            self._error_mapper.raise_http(e, symbol=symbol)

    async def refresh(self) -> None:
        """Force refresh the provider. Raises HTTPException on failure."""
        try:
            await self._provider.refresh()
        except _PROVIDER_EXCEPTIONS as e:
            self._error_mapper.raise_http(e)

    async def stream(
        self,
        symbol_list: list[str],
        *,
        stop_event: asyncio.Event | None = None,
    ) -> AsyncIterator[MarketQuote]:
        """Stream real-time quotes for the given symbols.

        Pass stop_event when streaming over WebSocket so one client disconnect
        does not stop other clients (per-stream cancellation).
        """
        normalized = [self._normalize_symbol(s) for s in symbol_list]
        async for quote in self._provider.stream(
            normalized, stop_event=stop_event
        ):
            yield quote

    async def list_markets(
        self,
        active: bool = True,
        limit: int = 100,
        tag_id: str | None = None,
    ) -> list[MarketQuote]:
        """List prediction markets. Raises HTTPException if provider doesn't support it."""
        if not isinstance(self._provider, ListMarketsProvider):
            self._error_mapper.raise_http(
                NotImplementedError("Provider does not support list_markets")
            )
        try:
            return await self._provider.list_markets(
                active=active, limit=limit, tag_id=tag_id
            )
        except _PROVIDER_EXCEPTIONS as e:
            self._error_mapper.raise_http(e, symbol=None)

    async def handle_websocket_stream(
        self, websocket: WebSocket, symbols_required_message: str
    ) -> None:
        """Accept WebSocket, parse symbols from query params, and stream quotes."""
        # TODO: Add rate limit per connection / IP for WebSocket streams
        symbol_list = parse_symbols_param(
            websocket.query_params, normalizer=self._normalize
        )
        await handle_websocket_stream(
            websocket, self, symbol_list, symbols_required_message
        )
