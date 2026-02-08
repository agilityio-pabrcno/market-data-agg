"""Polymarket-specific models for prediction market metadata."""
from pydantic import BaseModel, Field


class PolymarketQuoteMetadata(BaseModel):
    """Minimal metadata for a Polymarket MarketQuote.

    Only what is needed: clob_token_ids for stream, slug/condition_id for identity,
    top_outcome for display. Omit fields when not present.
    """

    clob_token_ids: list[str] = Field(default_factory=list)
    condition_id: str | None = None
    slug: str | None = None
    top_outcome: str | None = None

    def to_metadata_dict(self) -> dict:
        """JSON-serializable dict for MarketQuote.metadata."""
        return self.model_dump()
