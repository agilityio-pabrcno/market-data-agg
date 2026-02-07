"""Shared utilities for market data providers."""

DECIMALS = 2


def round2(x: float | None) -> float | None:
    """Round a value to 2 decimal places; preserve None."""
    if x is None:
        return None
    return round(float(x), DECIMALS)
