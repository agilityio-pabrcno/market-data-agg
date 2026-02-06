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
from market_data_agg.providers.polymarket.models import PolymarketQuoteMetadata
from market_data_agg.schemas import MarketQuote, StreamMessage


class PolymarketProvider(MarketProvider):
    """Market data provider for Polymarket prediction markets.

    Uses the Gamma API for market metadata and the CLOB API for prices.
    Polymarket has a complex structure: Event -> Markets -> Outcomes.
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

        # Cache: slug -> market data
        self._market_cache: dict[str, dict[str, Any]] = {}
        # Cache: token_id -> (slug, outcome_index)
        self._token_to_market: dict[str, tuple[str, int]] = {}

    async def _fetch_market_by_slug(self, slug: str) -> dict[str, Any]:
        """Fetch market data from Gamma API by slug."""
        if slug in self._market_cache:
            return self._market_cache[slug]

        response = await self._gamma_client.get(
            "/markets",
            params={"slug": slug, "limit": 1},
        )
        response.raise_for_status()
        markets = response.json()

        if not markets:
            raise ValueError(f"Market with slug '{slug}' not found")

        market = markets[0]
        self._market_cache[slug] = market

        # Cache token ID mappings
        token_ids = market.get("clobTokenIds", [])
        for i, token_id in enumerate(token_ids):
            self._token_to_market[token_id] = (slug, i)

        return market

    async def _fetch_market_by_condition_id(self, condition_id: str) -> dict[str, Any]:
        """Fetch market data from Gamma API by condition ID."""
        response = await self._gamma_client.get(
            "/markets",
            params={"condition_id": condition_id, "limit": 1},
        )
        response.raise_for_status()
        markets = response.json()

        if not markets:
            raise ValueError(f"Market with condition_id '{condition_id}' not found")

        market = markets[0]
        slug = market.get("slug", condition_id)
        self._market_cache[slug] = market

        token_ids = market.get("clobTokenIds", [])
        for i, token_id in enumerate(token_ids):
            self._token_to_market[token_id] = (slug, i)

        return market

    async def _get_market(self, symbol: str) -> dict[str, Any]:
        """Get market data by slug or condition ID.

        Args:
            symbol: Market slug (e.g., "will-bitcoin-reach-100k") or condition ID.

        Returns:
            Market data dictionary.
        """
        # Check cache first
        if symbol in self._market_cache:
            return self._market_cache[symbol]

        # Try as slug first
        if not symbol.startswith("0x"):
            try:
                return await self._fetch_market_by_slug(symbol)
            except ValueError:
                pass

        # Try as condition ID
        return await self._fetch_market_by_condition_id(symbol)

    def _parse_outcome_prices(self, market: dict[str, Any]) -> list[float]:
        """Parse outcome prices from market data.

        Polymarket stores outcomePrices as a JSON string like '["0.65","0.35"]'.
        """
        prices_str = market.get("outcomePrices", "[]")
        if isinstance(prices_str, str):
            prices = json.loads(prices_str)
        else:
            prices = prices_str

        return [float(p) for p in prices]

    def _parse_outcomes(self, market: dict[str, Any]) -> list[str]:
        """Parse outcomes from market data."""
        outcomes_str = market.get("outcomes", "[]")
        if isinstance(outcomes_str, str):
            return json.loads(outcomes_str)
        return outcomes_str

    def _market_to_quote(
        self, market: dict[str, Any], outcome_index: int = 0
    ) -> MarketQuote:
        """Convert Polymarket market data to a MarketQuote.

        Args:
            market: Market data from Gamma API.
            outcome_index: Which outcome to use (0 = first, usually "Yes").

        Returns:
            MarketQuote with probability as value (0-1).
        """
        prices = self._parse_outcome_prices(market)
        outcomes = self._parse_outcomes(market)
        slug = market.get("slug", market.get("conditionId", "unknown"))

        # Get the probability for the specified outcome
        value = prices[outcome_index] if outcome_index < len(prices) else 0.0

        # Parse timestamp
        updated_at = market.get("updatedAt")
        if updated_at:
            try:
                timestamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Parse volume
        volume_str = market.get("volume")
        volume = float(volume_str) if volume_str else None

        metadata = PolymarketQuoteMetadata(
            question=market.get("question"),
            outcomes=outcomes,
            outcome_prices=prices,
            condition_id=market.get("conditionId"),
            clob_token_ids=market.get("clobTokenIds", []),
            outcome_index=outcome_index,
            outcome=outcomes[outcome_index] if outcome_index < len(outcomes) else None,
        )

        return MarketQuote(
            source=Source.POLYMARKET,
            symbol=slug,
            value=value,
            volume=volume,
            timestamp=timestamp,
            metadata=metadata.to_metadata_dict(),
        )

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current probability for a prediction market.

        Args:
            symbol: Market slug or condition ID.

        Returns:
            MarketQuote with probability (0-1) as value.
        """
        market = await self._get_market(symbol)
        return self._market_to_quote(market)

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        """Fetch historical data for a prediction market.

        Note: Polymarket's historical data is limited. This fetches the
        current state and returns a single quote. For real historical data,
        consider using their timeseries API if available.

        Args:
            symbol: Market slug or condition ID.
            start: Start of time range (not used - limited API).
            end: End of time range (not used - limited API).

        Returns:
            List with current quote (historical API is limited).
        """
        # Polymarket doesn't have a public historical API for prices
        # Return current quote as a single data point
        market = await self._get_market(symbol)
        quote = self._market_to_quote(market)
        return [quote]

    async def stream(self, symbols: list[str]) -> AsyncIterator[StreamMessage]:
        """Stream real-time price updates for prediction markets.

        Uses WebSocket connection to CLOB for real-time updates.

        Args:
            symbols: List of market slugs or condition IDs.

        Yields:
            StreamMessage objects with probability updates.
        """
        self._streaming = True

        # Resolve symbols to token IDs
        asset_ids: list[str] = []
        for symbol in symbols:
            market = await self._get_market(symbol)
            token_ids = market.get("clobTokenIds", [])
            asset_ids.extend(token_ids)

        if not asset_ids:
            return

        try:
            async with websockets.connect(self.CLOB_WSS_URL) as ws:
                self._ws = ws

                # Subscribe to market channel
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

                        # Handle last_trade_price events
                        if event_type == "last_trade_price":
                            asset_id = data.get("asset_id")
                            price = float(data.get("price", 0))
                            timestamp_ms = data.get("timestamp")

                            # Look up the market slug from token ID
                            if asset_id in self._token_to_market:
                                slug, _ = self._token_to_market[asset_id]
                            else:
                                slug = asset_id

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

                        # Handle price_change events
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
                                # Use best_bid as indicative price
                                best_bid = change.get("best_bid")
                                if not best_bid or best_bid == "0":
                                    continue

                                price = float(best_bid)

                                if asset_id in self._token_to_market:
                                    slug, _ = self._token_to_market[asset_id]
                                else:
                                    slug = asset_id

                                yield StreamMessage(
                                    source=Source.POLYMARKET,
                                    symbol=slug,
                                    price=price,
                                    timestamp=timestamp,
                                )

                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive
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
                self._market_cache[slug] = market

                # Cache token mappings
                token_ids = market.get("clobTokenIds", [])
                for i, token_id in enumerate(token_ids):
                    self._token_to_market[token_id] = (slug, i)

                quotes.append(self._market_to_quote(market))

        return quotes

    async def refresh(self) -> None:
        """Clear caches and reconnect."""
        self._market_cache.clear()
        self._token_to_market.clear()

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
