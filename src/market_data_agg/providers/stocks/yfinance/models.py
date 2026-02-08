"""Models for YFinance provider (history bar metadata, etc.)."""
from pydantic import BaseModel


class YFinanceBarMetadata(BaseModel):
    """Metadata for a single history bar (OHLC + provider)."""

    open: float
    high: float
    low: float
    provider: str = "yfinance"
