"""Domain concept for mapping provider exceptions to HTTP responses."""
import asyncio
from dataclasses import dataclass

import httpx

from fastapi import HTTPException


@dataclass(frozen=True)
class ProviderErrorMapper:
    """Maps provider/backend exceptions to HTTP (status_code, detail).

    Inject this into services to centralize error-to-HTTP mapping per domain
    (e.g. crypto, stocks, predictions) with appropriate resource and API names.
    """

    resource_name: str = "Resource"
    api_name: str = "API"

    def to_http(
        self,
        exc: Exception,
        symbol: str | None = None,
    ) -> tuple[int, str]:
        """Map a provider exception to (status_code, detail) for HTTP responses.

        Args:
            exc: The exception raised by the provider or service.
            symbol: Optional symbol/identifier to include in detail (e.g. "AAPL").

        Returns:
            (status_code, detail) suitable for HTTPException(status_code=..., detail=...).
        """
        if isinstance(exc, ValueError):
            detail = str(exc) or f"{self.resource_name} not found"
            if symbol is not None and "not found" in detail.lower():
                detail = f"{self.resource_name} '{symbol}' not found"
            return (404, detail)
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == 404:
                detail = (
                    f"{self.resource_name} not found"
                    if symbol is None
                    else f"{self.resource_name} '{symbol}' not found"
                )
                return (404, detail)
            if status >= 500:
                return (502, f"{self.api_name} error")
            return (status, f"{self.api_name} error")
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            detail = "Request timed out"
            if symbol is not None:
                detail = f"Request to {self.api_name} timed out for '{symbol}'"
            return (504, detail)
        if isinstance(exc, (KeyError, TypeError)):
            detail = (
                f"{self.resource_name} not found"
                if symbol is None
                else f"{self.resource_name} '{symbol}' not found"
            )
            return (404, detail)
        return (500, "Internal server error")

    def raise_http(
        self,
        exc: Exception,
        symbol: str | None = None,
    ) -> None:
        """Map provider exception to HTTP and raise HTTPException. Never returns."""
        status_code, detail = self.to_http(exc, symbol=symbol)
        raise HTTPException(status_code=status_code, detail=detail) from exc
