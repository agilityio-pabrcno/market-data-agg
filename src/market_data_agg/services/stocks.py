"""Stocks service: quote, overview, history, refresh, stream with unified error mapping."""
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from fastapi import WebSocket

from market_data_agg.providers import MarketProviderABC, raise_provider_http
from market_data_agg.schemas import MarketQuote
from market_data_agg.services.utils import (
    handle_websocket_stream,
    parse_symbols_param,
)


class StocksService:
    """Thin service over stocks provider; maps provider errors to HTTP."""

    def __init__(self, provider: MarketProviderABC) -> None:
        self._provider = provider

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Get current quote for a stock symbol. Raises HTTPException on provider errors."""
        try:
            return await self._provider.get_quote(symbol.upper())
        except Exception as e:
            raise_provider_http(e, resource_name="Stock", symbol=symbol, api_name="Stocks API")

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Get overview (main) stock quotes. Raises HTTPException on provider errors."""
        try:
            return await self._provider.get_overview_quotes()
        except Exception as e:
            raise_provider_http(e, resource_name="Stocks", api_name="Stocks API")

    async def get_history(self, symbol: str, days: int) -> list[MarketQuote]:
        """Get historical quotes for a stock. Raises HTTPException on provider errors."""
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        try:
            return await self._provider.get_history(symbol.upper(), start, end)
        except Exception as e:
            raise_provider_http(
                e,
                resource_name="History for stock",
                symbol=symbol,
                api_name="Stocks API",
            )

    async def refresh(self) -> None:
        """Force refresh the stocks provider. Raises HTTPException on failure."""
        try:
            await self._provider.refresh()
        except Exception as e:
            raise_provider_http(e, resource_name="Stocks", api_name="Stocks API")

    async def stream(self, symbol_list: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream real-time quotes for the given symbols."""
        async for quote in self._provider.stream(symbol_list):
            yield quote

    async def handle_websocket_stream(
        self, websocket: WebSocket, symbols_required_message: str
    ) -> None:
        """Accept WebSocket, parse symbols from query params, and stream quotes."""
        symbol_list = parse_symbols_param(websocket.query_params, normalizer=str.upper)
        await handle_websocket_stream(
            websocket, self, symbol_list, symbols_required_message
        )
