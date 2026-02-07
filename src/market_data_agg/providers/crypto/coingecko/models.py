"""Models for CoinGecko provider (quote metadata and API params)."""
from pydantic import BaseModel, Field


class CoinGeckoQuoteMetadata(BaseModel):
    """Metadata for a crypto quote (market cap and 24h change)."""

    market_cap: float | None = None
    change_24h: float | None = None


class CoinGeckoSimplePriceParams(BaseModel):
    """Params for /simple/price (get_quote). Merge with 'ids' at call site."""

    vs_currencies: str = "usd"
    include_market_cap: str = "true"
    include_24hr_vol: str = "true"
    include_24hr_change: str = "true"
    include_last_updated_at: str = "true"


class CoinGeckoStreamPriceParams(BaseModel):
    """Params for /simple/price (stream). Merge with 'ids' at call site."""

    vs_currencies: str = "usd"
    include_last_updated_at: str = "true"


class CoinGeckoMarketsParams(BaseModel):
    """Params for /coins/markets (get_overview_quotes)."""

    vs_currency: str = "usd"
    per_page: int = 10
    page: int = 1
    sparkline: str = "false"


class CoinGeckoHistoryParams(BaseModel):
    """Params for /coins/{id}/market_chart/range (get_history)."""

    vs_currency: str = "usd"
    from_ts: int = Field(serialization_alias="from")
    to_ts: int = Field(serialization_alias="to")

    model_config = {"populate_by_name": True}
