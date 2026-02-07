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
from market_data_agg.providers.predictions.predictions_provider_abc import (
    PredictionsProviderABC,
)
from market_data_agg.providers.predictions.polymarket.dto import (
    PolymarketEventDTO,
    PolymarketMarketDTO,
)
from market_data_agg.schemas import MarketQuote


class PolymarketProvider(PredictionsProviderABC):
    """Market data provider for Polymarket prediction markets.

    Uses the Gamma API for market metadata and the CLOB API for prices.
    Fetches markets as DTOs and uses DTO.to_market_quote() for unified MarketQuote output.
    """

    GAMMA_API_URL = "https://gamma-api.polymarket.com"
    CLOB_WSS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __init__(self, poll_interval: float = 5.0) -> None:
        """Initialize the Polymarket provider.

        Args:
            poll_interval: Reserved for future polling-based fallback.
        """
        self._poll_interval = poll_interval
        self._gamma_client = httpx.AsyncClient(base_url=self.GAMMA_API_URL)
        self._streaming = False
        self._ws: ClientConnection | None = None

    async def _fetch_market(self, symbol: str) -> PolymarketMarketDTO:
        """Fetch a single market by slug from the Gamma API.

        Symbol must be the market slug (e.g. "will-bitcoin-hit-100k"), as in
        the Polymarket URL path. Condition IDs (0x...) are not supported.
        """
        response = await self._gamma_client.get(
            "/markets",
            params={"slug": symbol, "limit": 1},
        )
        response.raise_for_status()
        markets = response.json()
        if not markets:
            raise ValueError(f"Market not found: {symbol}")
        return PolymarketMarketDTO.model_validate(markets[0])

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current probability for a prediction market.

        Args:
            symbol: Market slug (e.g. from the Polymarket URL).

        Returns:
            MarketQuote with symbol=question, value=max outcome probability, volume=total USD.
        """
        market_dto = await self._fetch_market(symbol)
        return market_dto.to_market_quote()

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Fetch active prediction markets for overview."""
        return await self.list_markets(active=True, limit=5)

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        raise NotImplementedError("Historical data is not supported by this provider")

    async def stream(self, symbols: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream real-time price updates for prediction markets.

        Uses WebSocket connection to CLOB for real-time updates.

        Args:
            symbols: List of market slugs.

        Yields:
            MarketQuote objects with probability updates.
        """
        self._streaming = True

        # Map CLOB token IDs -> symbol (question) for consistent MarketQuote.symbol
        token_to_symbol: dict[str, str] = {}
        asset_ids: list[str] = []
        for slug in symbols:
            market_dto = await self._fetch_market(slug)
            question = market_dto.symbol  # question or slug fallback
            for token_id in market_dto.clob_token_ids_parsed:
                token_to_symbol[token_id] = question
            asset_ids.extend(market_dto.clob_token_ids_parsed)

        if not asset_ids:
            return

        def _timestamp_from_msg(data: dict) -> datetime:
            ts = data.get("timestamp")
            if ts is not None:
                try:
                    return datetime.fromtimestamp(int(ts) / 1000)
                except (ValueError, TypeError):
                    pass
            return datetime.utcnow()

        def _quote_for(asset_id: str, price: float, ts: datetime) -> MarketQuote:
            symbol = token_to_symbol.get(asset_id, asset_id)
            return MarketQuote(
                source=Source.EVENTS,
                symbol=symbol,
                value=price,
                volume=None,
                timestamp=ts,
                metadata=None,
            )

        try:
            async with websockets.connect(self.CLOB_WSS_URL) as ws:
                self._ws = ws
                await ws.send(
                    json.dumps({"type": "MARKET", "assets_ids": asset_ids})
                )

                while self._streaming:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        data = json.loads(raw)
                        event_type = data.get("event_type")
                        ts = _timestamp_from_msg(data)

                        if event_type == "last_trade_price":
                            asset_id = data.get("asset_id")
                            if asset_id is not None:
                                price = float(data.get("price", 0))
                                yield _quote_for(asset_id, price, ts)
                        if event_type == "price_change":
                            for change in data.get("price_changes") or []:
                                asset_id = change.get("asset_id")
                                best_bid = change.get("best_bid")
                                if asset_id is None or not best_bid or best_bid == "0":
                                    continue
                                yield _quote_for(
                                    asset_id, float(best_bid), ts
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
        events_data = response.json()

        quotes: list[MarketQuote] = []
        for event_data in events_data:
            event_dto = PolymarketEventDTO.model_validate(event_data)
            for market_dto in event_dto.markets:
                quotes.append(market_dto.to_market_quote())

        return quotes

    async def refresh(self) -> None:
        """Close WebSocket so the next stream() opens a fresh connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def close(self) -> None:
        """Close Gamma HTTP client and WebSocket."""
        self._streaming = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        await self._gamma_client.aclose()
