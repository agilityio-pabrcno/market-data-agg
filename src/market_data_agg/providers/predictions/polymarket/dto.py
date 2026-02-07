"""Data Transfer Objects for Polymarket API responses.

DTOs represent the external API structure and compile parsed/derived fields.
PolymarketMarketDTO validates raw API data, parses JSON strings, and can produce
MarketQuote directly (value = max probability, symbol = question, volume = total USD).
"""
import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from market_data_agg.db import Source
from market_data_agg.providers.predictions.polymarket.models import (
    PolymarketQuoteMetadata,
)
from market_data_agg.schemas import MarketQuote


def _parse_outcomes(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    return list(raw)


def _parse_outcome_prices(raw: str | list[str] | None) -> list[float]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        arr = raw
    return [float(p) for p in arr]


def _parse_clob_token_ids(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        if raw.strip().startswith("["):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return [tid.strip() for tid in raw.split(",") if tid.strip()]
    return list(raw)


class PolymarketMarketDTO(BaseModel):
    """DTO for a market from Polymarket's Gamma API.

    Validates raw API fields and compiles parsed/derived fields. Use
    to_market_quote() to get a MarketQuote (symbol=question, value=max prob, volume=total).
    """

    model_config = ConfigDict(populate_by_name=True)

    # Core identifiers
    id: str | None = Field(default=None, description="Market ID")
    slug: str | None = Field(default=None, description="Market slug identifier")
    question: str | None = Field(default=None, description="Market question text")
    condition_id: str | None = Field(
        default=None, alias="conditionId", description="Polymarket condition ID (hex)"
    )

    # Raw market data (API may send JSON strings)
    outcomes: str | None = Field(
        default=None,
        description="Outcome labels as JSON string",
    )
    outcome_prices: str | None = Field(
        default=None,
        alias="outcomePrices",
        description="Outcome prices as JSON string",
    )
    clob_token_ids: str | None = Field(
        default=None,
        alias="clobTokenIds",
        description="CLOB token IDs as JSON string or comma-separated",
    )

    # Volume and liquidity
    volume: str | None = Field(default=None, description="Trading volume")
    volume_num: float | None = Field(
        default=None, alias="volumeNum", description="Volume as number"
    )
    liquidity: str | None = Field(default=None, description="Market liquidity")
    liquidity_num: float | None = Field(
        default=None, alias="liquidityNum", description="Liquidity as number"
    )

    # Timestamps
    updated_at: str | None = Field(
        default=None, alias="updatedAt", description="Last update timestamp"
    )
    created_at: str | None = Field(
        default=None, alias="createdAt", description="Creation timestamp"
    )
    end_date: str | None = Field(
        default=None, alias="endDate", description="Market end date"
    )
    start_date: str | None = Field(
        default=None, alias="startDate", description="Market start date"
    )

    # Market state
    active: bool | None = Field(default=None, description="Whether market is active")
    closed: bool | None = Field(default=None, description="Whether market is closed")
    enable_order_book: bool | None = Field(
        default=None,
        alias="enableOrderBook",
        description="Whether order book is enabled",
    )

    # Additional metadata
    description: str | None = Field(default=None, description="Market description")
    category: str | None = Field(default=None, description="Market category")
    image: str | None = Field(default=None, description="Market image URL")
    icon: str | None = Field(default=None, description="Market icon URL")

    # --- Compiled/parsed (from raw API fields) ---

    @computed_field
    @property
    def outcomes_parsed(self) -> list[str]:
        return _parse_outcomes(self.outcomes)

    @computed_field
    @property
    def outcome_prices_parsed(self) -> list[float]:
        return _parse_outcome_prices(self.outcome_prices)

    @computed_field
    @property
    def clob_token_ids_parsed(self) -> list[str]:
        return _parse_clob_token_ids(self.clob_token_ids)

    @computed_field
    @property
    def value(self) -> float:
        """Probability of the top outcome (0-1)."""
        prices = self.outcome_prices_parsed
        return max(prices) if prices else 0.0

    @computed_field
    @property
    def top_outcome_index(self) -> int:
        """Index of the outcome whose probability is value."""
        prices = self.outcome_prices_parsed
        if not prices:
            return 0
        return int(prices.index(max(prices)))

    @computed_field
    @property
    def top_outcome(self) -> str | None:
        """Label of the top outcome."""
        idx = self.top_outcome_index
        outcomes = self.outcomes_parsed
        return outcomes[idx] if idx < len(outcomes) else None

    @computed_field
    @property
    def symbol(self) -> str:
        """Symbol for MarketQuote: question, or slug/condition_id fallback."""
        return self.question or self.slug or self.condition_id or "unknown"

    @computed_field
    @property
    def volume_compiled(self) -> float | None:
        """Total USD volume for MarketQuote."""
        if self.volume_num is not None:
            return float(self.volume_num)
        if self.volume:
            try:
                return float(self.volume)
            except (ValueError, TypeError):
                pass
        return None

    @computed_field
    @property
    def timestamp_compiled(self) -> datetime:
        """Timestamp for MarketQuote from updated_at or now."""
        if self.updated_at:
            try:
                return datetime.fromisoformat(
                    self.updated_at.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass
        return datetime.utcnow()

    def to_metadata_dict(self) -> dict:
        """Return dict for MarketQuote.metadata (full Polymarket structure)."""
        meta = PolymarketQuoteMetadata(
            question=self.question,
            outcomes=self.outcomes_parsed,
            outcome_prices=self.outcome_prices_parsed,
            condition_id=self.condition_id,
            clob_token_ids=self.clob_token_ids_parsed,
            slug=self.slug,
            top_outcome_index=self.top_outcome_index,
            top_outcome=self.top_outcome,
        )
        return meta.to_metadata_dict()

    def to_market_quote(self) -> MarketQuote:
        """Build MarketQuote: symbol=question, value=max prob, volume=total USD."""
        return MarketQuote(
            source=Source.EVENTS,
            symbol=self.symbol,
            value=self.value,
            volume=self.volume_compiled,
            timestamp=self.timestamp_compiled,
            metadata=self.to_metadata_dict(),
        )

class PolymarketEventDTO(BaseModel):
    """DTO representing an event from Polymarket's Gamma API.

    Events contain one or more markets.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, description="Event ID")
    title: str | None = Field(default=None, description="Event title")
    slug: str | None = Field(default=None, description="Event slug")
    description: str | None = Field(default=None, description="Event description")
    markets: list[PolymarketMarketDTO] = Field(
        default_factory=list, description="Markets within this event"
    )
    active: bool | None = Field(default=None, description="Whether event is active")
    closed: bool | None = Field(default=None, description="Whether event is closed")
    start_date: str | None = Field(
        default=None, alias="startDate", description="Event start date"
    )
    end_date: str | None = Field(
        default=None, alias="endDate", description="Event end date"
    )
    liquidity: float | None = Field(default=None, description="Event liquidity")
    volume: float | None = Field(default=None, description="Event volume")


class PolymarketPriceUpdateDTO(BaseModel):
    """DTO representing a price update from Polymarket's CLOB WebSocket.

    This matches the structure of WebSocket messages for price updates.
    """

    model_config = ConfigDict(populate_by_name=True)

    event_type: str = Field(..., description="Type of event (last_trade_price, price_change)")
    asset_id: str | None = Field(default=None, description="CLOB token/asset ID")
    price: str | float | None = Field(default=None, description="Trade price")
    timestamp: str | int | None = Field(default=None, description="Timestamp in milliseconds")
    price_changes: list[dict] | None = Field(
        default=None, description="List of price changes (for price_change events)"
    )
