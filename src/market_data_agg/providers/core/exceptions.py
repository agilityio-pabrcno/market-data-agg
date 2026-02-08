"""Shared exception-to-HTTP mapping for provider and API errors.

Prefer injecting ProviderErrorMapper into services for domain-specific mapping.
These functions remain for one-off or legacy use.
"""
from market_data_agg.providers.core.error_mapper import ProviderErrorMapper


def provider_error_to_http(
    exc: Exception,
    resource_name: str = "Resource",
    symbol: str | None = None,
    api_name: str = "API",
) -> tuple[int, str]:
    """Map a provider/backend exception to (status_code, detail) for HTTP responses.

    Prefer ProviderErrorMapper for injectable, domain-specific error mapping.
    """
    mapper = ProviderErrorMapper(resource_name=resource_name, api_name=api_name)
    return mapper.to_http(exc, symbol=symbol)


def raise_provider_http(
    exc: Exception,
    resource_name: str = "Resource",
    symbol: str | None = None,
    api_name: str = "API",
) -> None:
    """Map provider exception to HTTP and raise HTTPException. Never returns.

    Prefer ProviderErrorMapper for injectable, domain-specific error mapping.
    """
    mapper = ProviderErrorMapper(resource_name=resource_name, api_name=api_name)
    mapper.raise_http(exc, symbol=symbol)
