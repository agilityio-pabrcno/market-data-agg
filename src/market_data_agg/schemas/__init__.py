"""Pydantic schemas for API and runtime use. Not persisted to DB."""
from datetime import datetime

from pydantic import BaseModel


class MarketQuote(BaseModel):
    """Unified quote across providers (stock, crypto, polymarket)."""

    source: str  # stock | crypto | polymarket
    symbol: str
    value: float  # price or probability (0–1 for prediction markets)
    volume: float | None = None
    timestamp: datetime = ...
    metadata: dict | None = None


class StreamMessage(BaseModel):
    """WebSocket push payload for real-time streaming."""

    source: str
    symbol: str
    price: float
    timestamp: datetime


__all__ = ["MarketQuote", "StreamMessage"]
