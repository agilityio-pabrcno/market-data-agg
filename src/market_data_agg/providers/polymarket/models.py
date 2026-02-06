"""Polymarket-specific models for prediction market metadata."""
from pydantic import BaseModel, Field


class PolymarketQuoteMetadata(BaseModel):
    """Metadata attached to a MarketQuote when the source is Polymarket.

    Captures the prediction market structure: question, outcomes (e.g. Yes/No),
    their prices (probabilities), CLOB token IDs, and which outcome this quote refers to.
    """

    question: str | None = Field(default=None, description="Market question text")
    outcomes: list[str] = Field(
        default_factory=list,
        description="Outcome labels (e.g. ['Yes', 'No'])",
    )
    outcome_prices: list[float] = Field(
        default_factory=list,
        description="Probability/price per outcome (0–1), same order as outcomes",
    )
    condition_id: str | None = Field(
        default=None,
        description="Polymarket condition ID (hex)",
    )
    clob_token_ids: list[str] = Field(
        default_factory=list,
        description="CLOB token IDs for each outcome (for WebSocket subscriptions)",
    )
    outcome_index: int = Field(
        default=0,
        description="Index of the outcome this quote's value refers to",
    )
    outcome: str | None = Field(
        default=None,
        description="Label of the outcome this quote's value refers to (e.g. 'Yes')",
    )

    def to_metadata_dict(self) -> dict:
        """Return a dict suitable for MarketQuote.metadata (JSON-serializable)."""
        return self.model_dump()
