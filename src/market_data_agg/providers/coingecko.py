"""CoinGecko market data provider for cryptocurrencies."""
import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from market_data_agg.db import Source
from market_data_agg.providers.base import MarketProvider
from market_data_agg.schemas import MarketQuote, StreamMessage


class CoinGeckoProvider(MarketProvider):
    """Market data provider for cryptocurrencies via CoinGecko API.

    Uses CoinGecko IDs as symbols (e.g., "bitcoin", "ethereum", "solana").
    See https://api.coingecko.com/api/v3/coins/list for all available IDs.

    Uses httpx for REST calls and implements polling-based streaming
    as a fallback (CoinGecko WebSocket requires paid plan).
    """

    BASE_URL = "https://api.coingecko.com/api/v3"
    PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3"

    def __init__(
        self,
        api_key: str | None = None,
        use_pro_api: bool = False,
        poll_interval: float = 10.0,
    ) -> None:
        """Initialize the CoinGecko provider.

        Args:
            api_key: CoinGecko API key. Defaults to COINGECKO_API_KEY env var.
            use_pro_api: Whether to use the Pro API endpoint.
            poll_interval: Interval in seconds for polling-based streaming.
        """
        self._api_key = api_key or os.getenv("COINGECKO_API_KEY")
        self._use_pro_api = use_pro_api or bool(self._api_key)
        self._poll_interval = poll_interval
        self._streaming = False

        # Build headers
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            headers["x-cg-pro-api-key"] = self._api_key

        base_url = self.PRO_BASE_URL if self._use_pro_api else self.BASE_URL
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers)

    def _normalize_id(self, symbol: str) -> str:
        """Normalize a CoinGecko ID (lowercase)."""
        return symbol.lower()

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current quote for a cryptocurrency.

        Args:
            symbol: CoinGecko ID (e.g., "bitcoin", "ethereum").

        Returns:
            MarketQuote with the current price.
        """
        coin_id = self._normalize_id(symbol)

        response = await self._client.get(
            "/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            },
        )
        response.raise_for_status()
        data = response.json()

        if coin_id not in data:
            raise ValueError(f"Coin '{coin_id}' not found")

        coin_data = data[coin_id]
        last_updated = coin_data.get("last_updated_at")
        timestamp = (
            datetime.fromtimestamp(last_updated)
            if last_updated
            else datetime.utcnow()
        )

        return MarketQuote(
            source=Source.CRYPTO,
            symbol=coin_id,
            value=float(coin_data["usd"]),
            volume=float(coin_data.get("usd_24h_vol", 0)) or None,
            timestamp=timestamp,
            metadata={
                "market_cap": coin_data.get("usd_market_cap"),
                "change_24h": coin_data.get("usd_24h_change"),
            },
        )

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketQuote]:
        """Fetch historical price data for a cryptocurrency.

        Args:
            symbol: CoinGecko ID (e.g., "bitcoin", "ethereum").
            start: Start of time range.
            end: End of time range.

        Returns:
            List of MarketQuotes ordered by timestamp.
        """
        coin_id = self._normalize_id(symbol)

        # CoinGecko uses UNIX timestamps in seconds
        from_ts = int(start.timestamp())
        to_ts = int(end.timestamp())

        response = await self._client.get(
            f"/coins/{coin_id}/market_chart/range",
            params={
                "vs_currency": "usd",
                "from": from_ts,
                "to": to_ts,
            },
        )
        response.raise_for_status()
        data = response.json()

        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        market_caps = data.get("market_caps", [])

        # Create a volume lookup by timestamp (CoinGecko returns ms timestamps)
        volume_map = {int(v[0]): v[1] for v in volumes}
        mcap_map = {int(m[0]): m[1] for m in market_caps}

        quotes: list[MarketQuote] = []
        for price_point in prices:
            ts_ms = int(price_point[0])
            price = price_point[1]
            timestamp = datetime.fromtimestamp(ts_ms / 1000)

            quotes.append(
                MarketQuote(
                    source=Source.CRYPTO,
                    symbol=coin_id,
                    value=float(price),
                    volume=float(volume_map.get(ts_ms, 0)) or None,
                    timestamp=timestamp,
                    metadata={
                        "market_cap": mcap_map.get(ts_ms),
                    },
                )
            )

        return quotes

    async def stream(self, symbols: list[str]) -> AsyncIterator[StreamMessage]:
        """Stream real-time price updates via polling.

        CoinGecko WebSocket requires a paid plan, so this implementation
        polls the REST API at regular intervals.

        Args:
            symbols: List of CoinGecko IDs to stream (e.g., ["bitcoin", "ethereum"]).

        Yields:
            StreamMessage objects with price updates.
        """
        self._streaming = True
        coin_ids = [self._normalize_id(s) for s in symbols]
        ids_param = ",".join(coin_ids)

        # Track last prices to only emit on change
        last_prices: dict[str, float] = {}

        try:
            while self._streaming:
                response = await self._client.get(
                    "/simple/price",
                    params={
                        "ids": ids_param,
                        "vs_currencies": "usd",
                        "include_last_updated_at": "true",
                    },
                )
                response.raise_for_status()
                data = response.json()

                for coin_id in coin_ids:
                    if coin_id not in data:
                        continue

                    coin_data = data[coin_id]
                    price = float(coin_data["usd"])

                    # Only emit if price changed
                    if coin_id in last_prices and last_prices[coin_id] == price:
                        continue

                    last_prices[coin_id] = price

                    last_updated = coin_data.get("last_updated_at")
                    timestamp = (
                        datetime.fromtimestamp(last_updated)
                        if last_updated
                        else datetime.utcnow()
                    )

                    yield StreamMessage(
                        source=Source.CRYPTO,
                        symbol=coin_id,
                        price=price,
                        timestamp=timestamp,
                    )

                await asyncio.sleep(self._poll_interval)
        finally:
            self._streaming = False

    async def refresh(self) -> None:
        """Force refresh - no-op for REST-based provider."""
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        self._streaming = False
        await self._client.aclose()
