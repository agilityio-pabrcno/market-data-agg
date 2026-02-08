"""Shared utilities for market data aggregation."""

from datetime import datetime


def parse_timestamp(ts: float | None) -> datetime:
    """Convert optional Unix timestamp (seconds) to datetime; fallback to utcnow."""
    return datetime.fromtimestamp(ts) if ts is not None else datetime.utcnow()
