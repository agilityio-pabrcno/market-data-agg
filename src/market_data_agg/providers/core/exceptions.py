"""Shared exception-to-HTTP mapping for provider and API errors."""
import asyncio

import httpx

from fastapi import HTTPException


def provider_error_to_http(
    exc: Exception,
    resource_name: str = "Resource",
    symbol: str | None = None,
    api_name: str = "API",
) -> tuple[int, str]:
    """Map a provider/backend exception to (status_code, detail) for HTTP responses.

    Args:
        exc: The exception raised by the provider or service.
        resource_name: Label for 404 messages (e.g. "Stock", "Crypto", "Market").
        symbol: Optional symbol/identifier to include in detail (e.g. "AAPL").
        api_name: Label for upstream errors (e.g. "CoinGecko", "Predictions API").

    Returns:
        (status_code, detail) suitable for HTTPException(status_code=..., detail=...).
    """
    if isinstance(exc, ValueError):
        detail = str(exc) or f"{resource_name} not found"
        if symbol is not None and "not found" in detail.lower():
            detail = f"{resource_name} '{symbol}' not found"
        return (404, detail)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 404:
            detail = f"{resource_name} not found" if symbol is None else f"{resource_name} '{symbol}' not found"
            return (404, detail)
        if status >= 500:
            return (502, f"{api_name} error")
        return (status, f"{api_name} error")
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        detail = "Request timed out"
        if symbol is not None:
            detail = f"Request to {api_name} timed out for '{symbol}'"
        return (504, detail)
    if isinstance(exc, (KeyError, TypeError)):
        detail = f"{resource_name} not found"
        if symbol is not None:
            detail = f"{resource_name} '{symbol}' not found"
        return (404, detail)
    return (500, "Internal server error")


def raise_provider_http(
    exc: Exception,
    resource_name: str = "Resource",
    symbol: str | None = None,
    api_name: str = "API",
) -> None:
    """Map provider exception to HTTP and raise HTTPException. Never returns."""
    status_code, detail = provider_error_to_http(exc, resource_name, symbol, api_name)
    raise HTTPException(status_code=status_code, detail=detail) from exc
