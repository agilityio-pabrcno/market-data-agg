"""Data Transfer Objects for Polymarket API responses.

DTOs represent the external API structure and compile parsed/derived fields.
PolymarketMarketDTO validates raw API data, parses JSON strings, and can produce
MarketQuote directly (value = max probability, symbol = question, volume = total USD).
"""
import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from market_data_agg.db import Source
from market_data_agg.providers.core import round2
from market_data_agg.providers.predictions.polymarket.models import \
    PolymarketQuoteMetadata
from market_data_agg.schemas import MarketQuote


class PolymarketMarketDTO(BaseModel):
    """DTO for a market from Polymarket's Gamma API.

    Only fields needed for MarketQuote (symbol, value, volume, timestamp) and
    for stream (clob_token_ids). Extra API keys are ignored (Pydantic default).

    Decorators: @computed_field = include in dump/schema; @property = access as attribute.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # Symbol (question or fallbacks)
    question: str | None = None
    slug: str | None = None
    condition_id: str | None = Field(default=None, alias="conditionId")

    # Raw lists (API may send JSON strings or comma-separated)
    outcomes: str | None = None
    outcome_prices: str | None = Field(default=None, alias="outcomePrices")
    clob_token_ids: str | None = Field(default=None, alias="clobTokenIds")

    # Volume and time (for MarketQuote)
    volume: str | None = None
    volume_num: float | None = Field(default=None, alias="volumeNum")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    # --- Parser: API often sends JSON arrays or comma-separated strings ---

    @staticmethod
    def _parse_raw_list(
        raw: str | list | None,
        *,
        coerce_float: bool = False,
        allow_comma_split: bool = False,
    ) -> list:
        """Parse a field that may be None, a JSON array string, or already a list."""
        if raw is None:
            return []
        if isinstance(raw, list):
            arr = raw
        elif isinstance(raw, str):
            s = raw.strip()
            if allow_comma_split and not s.startswith("["):
                arr = [x.strip() for x in raw.split(",") if x.strip()]
            else:
                try:
                    arr = json.loads(raw)
                except json.JSONDecodeError:
                    return []
        else:
            return []
        if coerce_float:
            return [float(p) for p in arr]
        return [str(x) for x in arr]

    # --- Compiled/parsed (exposed via @computed_field + @property) ---

    @computed_field
    @property
    def outcomes_parsed(self) -> list[str]:
        return self._parse_raw_list(self.outcomes)

    @computed_field
    @property
    def outcome_prices_parsed(self) -> list[float]:
        return self._parse_raw_list(self.outcome_prices, coerce_float=True)

    @computed_field
    @property
    def clob_token_ids_parsed(self) -> list[str]:
        return self._parse_raw_list(self.clob_token_ids, allow_comma_split=True)

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
        """Minimal dict for MarketQuote.metadata (clob_token_ids, identity, top_outcome)."""
        return PolymarketQuoteMetadata(
            clob_token_ids=self.clob_token_ids_parsed,
            condition_id=self.condition_id,
            slug=self.slug,
            top_outcome=self.top_outcome,
        ).to_metadata_dict()

    def to_market_quote(self) -> MarketQuote:
        """Build MarketQuote: symbol=question, value=max prob, volume=total USD."""
        return MarketQuote(
            source=Source.PREDICTIONS,
            symbol=self.symbol,
            value=round2(self.value),
            volume=round2(self.volume_compiled),
            timestamp=self.timestamp_compiled,
            metadata=self.to_metadata_dict(),
        )

class PolymarketEventDTO(BaseModel):
    """Event from Gamma API: we only need the list of markets."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    markets: list[PolymarketMarketDTO] = Field(default_factory=list)


class PolymarketPriceUpdateDTO(BaseModel):
    """Price update from CLOB WebSocket (for stream)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    event_type: str
    asset_id: str | None = None
    price: str | float | None = None
    timestamp: str | int | None = None
    price_changes: list[dict] | None = None
    price_changes: list[dict] | None = None
    price_changes: list[dict] | None = None
