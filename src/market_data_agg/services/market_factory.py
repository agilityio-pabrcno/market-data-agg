"""Factory for creating MarketService instances with different provider configurations."""
from collections.abc import Callable

from market_data_agg.providers.core import (MarketProviderABC,
                                            ProviderErrorMapper)
from market_data_agg.services.market_service import MarketService


def create_market_service(
    provider: MarketProviderABC,
    resource_name: str,
    api_name: str,
    *,
    symbol_normalizer: Callable[[str], str] | None = None,
) -> MarketService:
    """Create a MarketService with the given provider and error mapping config.

    Args:
        provider: The market data provider (e.g. YFinanceProvider, CoinGeckoProvider).
        resource_name: Label for 404 messages (e.g. "Stock", "Crypto", "Market").
        api_name: Label for upstream errors (e.g. "CoinGecko", "Stocks API").
        symbol_normalizer: Optional normalizer for symbols (e.g. str.upper for stocks).

    Returns:
        A configured MarketService instance.
    """
    error_mapper = ProviderErrorMapper(resource_name=resource_name, api_name=api_name)
    return MarketService(
        provider,
        error_mapper,
        symbol_normalizer=symbol_normalizer,
    )
