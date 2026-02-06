"""Polymarket data provider for prediction markets."""
import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx
import websockets
from websockets import ClientConnection

from market_data_agg.db import Source
from market_data_agg.providers.base import MarketProvider
from market_data_agg.providers.polymarket.cache import PolymarketMarketCache
from market_data_agg.providers.polymarket.mapper import market_to_quote
from market_data_agg.providers.polymarket.resolver import \
    PolymarketSymbolResolver
from market_data_agg.schemas import MarketQuote, StreamMessage


class PolymarketProvider(MarketProvider):
    """Market data provider for Polymarket prediction markets.

    Uses the Gamma API for market metadata and the CLOB API for prices.
    Polymarket has a complex structure: Event -> Markets -> Outcomes.

    Orchestrates cache, symbol resolution, and mapping to produce
    unified MarketQuote and StreamMessage output.
    """

    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    CLOB_API_URL = "https://clob.polymarket.com"
    CLOB_WSS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __init__(self, poll_interval: float = 5.0) -> None:
        """Initialize the Polymarket provider.

        Args:
            poll_interval: Interval for polling-based fallback streaming.
        """
        self._poll_interval = poll_interval
        self._gamma_client = httpx.AsyncClient(base_url=self.GAMMA_API_URL)
        self._clob_client = httpx.AsyncClient(base_url=self.CLOB_API_URL)
        self._streaming = False
        self._ws: ClientConnection | None = None

        self._cache = PolymarketMarketCache()
        self._resolver = PolymarketSymbolResolver(self._gamma_client, self._cache)

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current probability for a prediction market.

        Args:
            symbol: Market slug or condition ID.

        Returns:
            MarketQuote with probability (0-1) as value.
        """
        market = await self._resolver.resolve(symbol)
        return market_to_quote(market)

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        raise NotImplementedError("Historical data is not supported by this provider")
   

    async def stream(self, symbols: list[str]) -> AsyncIterator[StreamMessage]:
        """Stream real-time price updates for prediction markets.

        Uses WebSocket connection to CLOB for real-time updates.

        Args:
            symbols: List of market slugs or condition IDs.

        Yields:
            StreamMessage objects with probability updates.
        """
        self._streaming = True

        asset_ids: list[str] = []
        for symbol in symbols:
            market = await self._resolver.resolve(symbol)
            token_ids = market.get("clobTokenIds", [])
            asset_ids.extend(token_ids)

        if not asset_ids:
            return

        try:
            async with websockets.connect(self.CLOB_WSS_URL) as ws:
                self._ws = ws

                subscribe_msg = {
                    "type": "MARKET",
                    "assets_ids": asset_ids,
                }
                await ws.send(json.dumps(subscribe_msg))

                while self._streaming:
                    try:
                        raw_msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        data = json.loads(raw_msg)

                        event_type = data.get("event_type")

                        if event_type == "last_trade_price":
                            asset_id = data.get("asset_id")
                            price = float(data.get("price", 0))
                            timestamp_ms = data.get("timestamp")

                            slug, _ = (
                                self._cache.get_slug_for_token(asset_id)
                                or (asset_id, 0)
                            )

                            timestamp = (
                                datetime.fromtimestamp(int(timestamp_ms) / 1000)
                                if timestamp_ms
                                else datetime.utcnow()
                            )

                            yield StreamMessage(
                                source=Source.POLYMARKET,
                                symbol=slug,
                                price=price,
                                timestamp=timestamp,
                            )

                        elif event_type == "price_change":
                            price_changes = data.get("price_changes", [])
                            timestamp_ms = data.get("timestamp")
                            timestamp = (
                                datetime.fromtimestamp(int(timestamp_ms) / 1000)
                                if timestamp_ms
                                else datetime.utcnow()
                            )

                            for change in price_changes:
                                asset_id = change.get("asset_id")
                                best_bid = change.get("best_bid")
                                if not best_bid or best_bid == "0":
                                    continue

                                price = float(best_bid)

                                slug, _ = (
                                    self._cache.get_slug_for_token(asset_id)
                                    or (asset_id, 0)
                                )

                                yield StreamMessage(
                                    source=Source.POLYMARKET,
                                    symbol=slug,
                                    price=price,
                                    timestamp=timestamp,
                                )

                    except asyncio.TimeoutError:
                        await ws.ping()

        except websockets.ConnectionClosed:
            pass
        finally:
            self._streaming = False
            self._ws = None

    async def list_markets(
        self,
        active: bool = True,
        limit: int = 100,
        tag_id: str | None = None,
    ) -> list[MarketQuote]:
        """List available prediction markets.

        Args:
            active: Filter for active markets only.
            limit: Maximum number of markets to return.
            tag_id: Optional tag ID to filter by category.

        Returns:
            List of MarketQuotes for available markets.
        """
        params: dict[str, Any] = {
            "active": str(active).lower(),
            "closed": "false",
            "limit": limit,
        }
        if tag_id:
            params["tag_id"] = tag_id

        response = await self._gamma_client.get("/events", params=params)
        response.raise_for_status()
        events = response.json()

        quotes: list[MarketQuote] = []
        for event in events:
            markets = event.get("markets", [])
            for market in markets:
                slug = market.get("slug", "")
                self._cache.set(slug, market)
                quotes.append(market_to_quote(market))

        return quotes

    async def refresh(self) -> None:
        """Clear caches and reconnect."""
        self._cache.clear()

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def close(self) -> None:
        """Clean up resources."""
        self._streaming = False

        if self._ws:
            await self._ws.close()
            self._ws = None

        await self._gamma_client.aclose()
        await self._clob_client.aclose()
        await self._clob_client.aclose()
