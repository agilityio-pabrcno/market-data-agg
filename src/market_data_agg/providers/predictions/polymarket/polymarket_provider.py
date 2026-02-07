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
from market_data_agg.providers.core import round2
from market_data_agg.providers.predictions.polymarket.dto import (
    PolymarketEventDTO, PolymarketMarketDTO)
from market_data_agg.providers.predictions.predictions_provider_abc import \
    PredictionsProviderABC
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

    async def stream(self, symbols: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream real-time price updates for prediction markets.

        Uses WebSocket connection to CLOB for real-time updates.

        Args:
            symbols: List of market slugs.

        Yields:
            MarketQuote objects with probability updates.
        """
        self._streaming = True
        token_to_symbol, asset_ids = await self._build_symbol_mapping(symbols)
        if not asset_ids:
            return

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
                        ts = self._parse_message_timestamp(data)
                        for quote in self._quotes_from_message(
                            data, token_to_symbol, ts
                        ):
                            yield quote
                    except asyncio.TimeoutError:
                        await ws.ping()

        except websockets.ConnectionClosed:
            pass
        finally:
            self._streaming = False
            self._ws = None

    async def _build_symbol_mapping(
        self, symbols: list[str]
    ) -> tuple[dict[str, str], list[str]]:
        """Build token_id -> symbol map and flat asset_ids from market slugs.

        The CLOB WebSocket identifies assets by opaque token IDs (e.g. 0x...),
        but callers pass human-readable slugs (e.g. "will-bitcoin-hit-100k").
        We fetch each market from Gamma to resolve slugs -> token IDs and to
        map token IDs back to the market question (symbol) for MarketQuote output.
        """
        token_to_symbol: dict[str, str] = {}
        asset_ids: list[str] = []
        for slug in symbols:
            market_dto = await self._fetch_market(slug)
            question = market_dto.symbol
            for token_id in market_dto.clob_token_ids_parsed:
                token_to_symbol[token_id] = question
            asset_ids.extend(market_dto.clob_token_ids_parsed)
        return token_to_symbol, asset_ids

    def _parse_message_timestamp(self, data: dict) -> datetime:
        """Parse timestamp from WS message; fallback to utcnow.

        CLOB messages may include a timestamp (ms since epoch) or omit it.
        We need a datetime for every MarketQuote; if absent or invalid,
        we use utcnow() so streaming never fails on malformed timestamps.
        """
        ts_raw = data.get("timestamp")
        if ts_raw is None:
            return datetime.utcnow()
        try:
            return datetime.fromtimestamp(int(ts_raw) / 1000)
        except (ValueError, TypeError):
            return datetime.utcnow()

    def _quote_from_price(
        self,
        asset_id: str,
        price: float,
        ts: datetime,
        token_to_symbol: dict[str, str],
    ) -> MarketQuote:
        """Build MarketQuote from asset_id, price, and timestamp.

        Centralizes the conversion so both last_trade_price and price_change
        events produce the same MarketQuote shape. Resolves asset_id to the
        human-readable symbol (market question) via token_to_symbol.
        """
        symbol = token_to_symbol.get(asset_id, asset_id)
        return MarketQuote(
            source=Source.PREDICTIONS,
            symbol=symbol,
            value=round2(price),
            volume=None,
            timestamp=ts,
            metadata=None,
        )

    def _quotes_from_message(
        self,
        data: dict,
        token_to_symbol: dict[str, str],
        ts: datetime,
    ) -> list[MarketQuote]:
        """Extract MarketQuotes from a single WS message.

        CLOB sends two event types we care about: last_trade_price (single
        asset) and price_change (multiple assets). Isolating this logic keeps
        stream() focused on the receive loop; we parse once and yield 0..N
        quotes per message.
        """
        event_type = data.get("event_type")

        if event_type == "last_trade_price":
            asset_id = data.get("asset_id")
            if asset_id is None:
                return []
            price = float(data.get("price", 0))
            return [self._quote_from_price(asset_id, price, ts, token_to_symbol)]

        if event_type == "price_change":
            return [
                self._quote_from_price(asset_id, float(best_bid), ts, token_to_symbol)
                for change in data.get("price_changes") or []
                if (asset_id := change.get("asset_id")) is not None
                and (best_bid := change.get("best_bid"))
                and best_bid != "0"
            ]

        return []

 

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
