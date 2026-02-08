"""Pydantic schemas for API and runtime use. Not persisted to DB."""
from datetime import datetime

from pydantic import BaseModel, Field

from market_data_agg.db import Source


class MarketQuote(BaseModel):
    """Unified quote across providers (stock, crypto, polymarket).

    For prediction markets (e.g. Polymarket): symbol is the market question,
    value is the probability of the top outcome (0-1), volume is total USD volume.
    """

    source: Source
    symbol: str
    value: float  # price, or for prediction markets: max outcome probability (0-1)
    volume: float | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict | None = None


__all__ = ["MarketQuote"]
