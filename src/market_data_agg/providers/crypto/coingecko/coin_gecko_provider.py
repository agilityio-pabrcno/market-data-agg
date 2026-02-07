"""CoinGecko market data provider for cryptocurrencies."""
import os
from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from market_data_agg.db import Source
from market_data_agg.providers.core import MarketProviderABC, round2
from market_data_agg.providers.core.utils import normalize_crypto_id
from market_data_agg.providers.core.stream_helpers import stream_by_polling
from market_data_agg.providers.crypto.coingecko.models import (
    CoinGeckoHistoryParams, CoinGeckoMarketsParams, CoinGeckoQuoteMetadata,
    CoinGeckoSimplePriceParams, CoinGeckoStreamPriceParams)
from market_data_agg.schemas import MarketQuote
from market_data_agg.utils import parse_timestamp


class CoinGeckoProvider(MarketProviderABC):
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
        super().__init__()
        self._api_key = api_key or os.getenv("COINGECKO_API_KEY")
        self._use_pro_api = use_pro_api or bool(self._api_key)
        self._poll_interval = poll_interval

        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key:
            headers["x-cg-pro-api-key"] = self._api_key

        base = self.PRO_BASE_URL if self._use_pro_api else self.BASE_URL
        self._client = httpx.AsyncClient(base_url=base, headers=headers)

    async def get_quote(self, symbol: str) -> MarketQuote:
        """Fetch the current quote for a cryptocurrency.

        Args:
            symbol: CoinGecko ID (e.g., "bitcoin", "ethereum").

        Returns:
            MarketQuote with the current price.
        """
        coin_id = normalize_crypto_id(symbol)
        params = CoinGeckoSimplePriceParams().model_dump() | {"ids": coin_id}
        response = await self._client.get("/simple/price", params=params)
        response.raise_for_status()
        data = response.json()

        if coin_id not in data:
            raise ValueError(f"Coin '{coin_id}' not found")

        row = data[coin_id]
        if not row or row.get("usd") is None:
            raise ValueError(f"Coin '{coin_id}' not found")

        return self._quote_from_simple_price(coin_id, row)

    async def get_overview_quotes(self) -> list[MarketQuote]:
        """Fetch top coins by market cap (single API call)."""
        params = CoinGeckoMarketsParams().model_dump()
        response = await self._client.get("/coins/markets", params=params)
        response.raise_for_status()
        return [self._quote_from_market_item(item) for item in response.json()]

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
        coin_id = normalize_crypto_id(symbol)
        params = CoinGeckoHistoryParams(
            from_ts=int(start.timestamp()),
            to_ts=int(end.timestamp()),
        ).model_dump(by_alias=True)
        response = await self._client.get(
            f"/coins/{coin_id}/market_chart/range",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])
        market_caps = data.get("market_caps", [])

        volume_by_ts = {int(v[0]): v[1] for v in volumes}
        mcap_by_ts = {int(m[0]): m[1] for m in market_caps}

        return [
            MarketQuote(
                source=Source.CRYPTO,
                symbol=coin_id,
                value=round2(float(price)),
                volume=round2(float(volume_by_ts.get(ts_ms, 0))) or None,
                timestamp=datetime.fromtimestamp(ts_ms / 1000),
                metadata=CoinGeckoQuoteMetadata(
                    market_cap=round2(mcap_by_ts.get(ts_ms)),
                ).model_dump(),
            )
            for (ts_ms, price) in (p[:2] for p in prices)
        ]

    async def stream(self, symbols: list[str]) -> AsyncIterator[MarketQuote]:
        """Stream real-time price updates via polling.

        CoinGecko WebSocket requires a paid plan, so this implementation
        polls the REST API at regular intervals.

        Args:
            symbols: List of CoinGecko IDs to stream (e.g., ["bitcoin", "ethereum"]).

        Yields:
            MarketQuote objects with price updates.
        """
        coin_ids = [normalize_crypto_id(s) for s in symbols]

        async def fetch_batch(syms: list[str]) -> list[MarketQuote]:
            ids = [normalize_crypto_id(s) for s in syms]
            params = CoinGeckoStreamPriceParams().model_dump() | {
                "ids": ",".join(ids),
            }
            response = await self._client.get("/simple/price", params=params)
            response.raise_for_status()
            data = response.json()
            out: list[MarketQuote] = []
            for cid in ids:
                if cid not in data:
                    continue
                row = data[cid]
                if row and row.get("usd") is not None:
                    out.append(self._quote_from_simple_price(cid, row))
            return out

        async for quote in stream_by_polling(
            self,
            coin_ids,
            self._poll_interval,
            fetch_batch,
            dedup_by_value=True,
        ):
            yield quote

    async def refresh(self) -> None:
        """Force refresh - no-op for REST-based provider."""

    async def close(self) -> None:
        """Close the HTTP client."""
        self.streaming = False
        await self._client.aclose()

    def _build_quote(
        self,
        symbol: str,
        value: float,
        volume: float | None,
        timestamp: datetime,
        market_cap: float | None = None,
        change_24h: float | None = None,
    ) -> MarketQuote:
        """Build a MarketQuote from normalized CoinGecko data."""
        meta = CoinGeckoQuoteMetadata(
            market_cap=round2(market_cap),
            change_24h=round2(change_24h),
        )
        return MarketQuote(
            source=Source.CRYPTO,
            symbol=symbol,
            value=round2(value),
            volume=round2(volume) if volume is not None else None,
            timestamp=timestamp,
            metadata=meta.model_dump(),
        )

    def _quote_from_simple_price(self, coin_id: str, data: dict) -> MarketQuote:
        """Build a MarketQuote from a /simple/price response row."""
        vol = data.get("usd_24h_vol")
        return self._build_quote(
            symbol=coin_id,
            value=float(data["usd"]),
            volume=float(vol) if vol is not None else None,
            timestamp=parse_timestamp(data.get("last_updated_at")),
            market_cap=data.get("usd_market_cap"),
            change_24h=data.get("usd_24h_change"),
        )

    def _quote_from_market_item(self, item: dict) -> MarketQuote:
        """Build a MarketQuote from a /coins/markets response item."""
        vol = item.get("total_volume")
        return self._build_quote(
            symbol=item["id"],
            value=float(item["current_price"]),
            volume=float(vol) if vol is not None else None,
            timestamp=datetime.utcnow(),
            market_cap=item.get("market_cap"),
            change_24h=item.get("price_change_percentage_24h"),
        )
