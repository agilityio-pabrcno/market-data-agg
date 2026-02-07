"""Predictions service: quote, overview, list_markets, refresh, stream with unified error mapping."""
from collections.abc import AsyncIterator

from fastapi import WebSocket

from market_data_agg.providers import PredictionsProviderABC
from market_data_agg.providers.core import raise_provider_http
from market_data_agg.schemas import MarketQuote
from market_data_agg.services.utils import (
    handle_websocket_stream,
    parse_symbols_param,
)


class PredictionsService:
    """Thin service over predictions provider; maps provider errors to HTTP."""

    def __init__(self, provider: PredictionsProviderABC) -> None:
        self._provider = provider

    async def get_quote(self, market_id: str) -> MarketQuote:
        """Get quote for a prediction market. Raises HTTPException on provider errors."""
        try:
            return await self._provider.get_quote(market_id)
        except Exception as e:
            raise_provider_http(
                e,
                resource_name="Market",
                symbol=market_id,
                api_name="Predictions API",
            )

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Get overview (active) prediction markets. Raises HTTPException on provider errors."""
        try:
            return await self._provider.get_overview_quotes()
        except Exception as e:
            raise_provider_http(e, resource_name="Predictions", api_name="Predictions API")

    async def list_markets(
        self,
        active: bool = True,
        limit: int = 100,
        tag_id: str | None = None,
    ) -> list[MarketQuote]:
        """List prediction markets. Raises HTTPException on provider errors."""
        try:
            return await self._provider.list_markets(active=active, limit=limit, tag_id=tag_id)
        except Exception as e:
            raise_provider_http(e, resource_name="Markets", api_name="Predictions API")

    async def refresh(self) -> None:
        """Force refresh the predictions provider. Raises HTTPException on failure."""
        try:
            await self._provider.refresh()
        except Exception as e:
            raise_provider_http(e, resource_name="Predictions", api_name="Predictions API")

    async def stream(self, symbol_list: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream real-time quotes for the given symbols."""
        async for quote in self._provider.stream(symbol_list):
            yield quote

    async def handle_websocket_stream(
        self, websocket: WebSocket, symbols_required_message: str
    ) -> None:
        """Accept WebSocket, parse symbols from query params, and stream quotes."""
        symbol_list = parse_symbols_param(websocket.query_params)
        await handle_websocket_stream(
            websocket, self, symbol_list, symbols_required_message
        )
