"""Pydantic schemas for API and runtime use. Not persisted to DB."""
from datetime import datetime

from pydantic import BaseModel, Field

from market_data_agg.db import Source


class MarketQuote(BaseModel):
    """Unified quote across providers (stock, crypto, polymarket)."""

    source: Source
    symbol: str
    value: float  # price or probability (0–1 for prediction markets)
    volume: float | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict | None = None


class StreamMessage(BaseModel):
    """WebSocket push payload for real-time streaming."""

    source: Source
    symbol: str
    price: float
    timestamp: datetime


__all__ = ["MarketQuote", "StreamMessage"]
