"""Shared utilities for market data providers."""

DECIMALS = 2


def normalize_stock_symbol(symbol: str) -> str:
    """Normalize a stock symbol (uppercase)."""
    return symbol.upper()


def normalize_crypto_id(symbol: str) -> str:
    """Normalize a CoinGecko/crypto ID (lowercase)."""
    return symbol.lower()


def round2(x: float | None) -> float | None:
    """Round a value to 2 decimal places; preserve None."""
    if x is None:
        return None
    return round(float(x), DECIMALS)
