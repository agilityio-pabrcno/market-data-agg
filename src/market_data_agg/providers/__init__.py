"""Market data providers for stocks, crypto, and prediction markets."""
from market_data_agg.providers.core import (MarketProviderABC,
                                            ProviderErrorMapper,
                                            provider_error_to_http,
                                            raise_provider_http)
from market_data_agg.providers.crypto import CoinGeckoProvider
from market_data_agg.providers.predictions import (PolymarketProvider,
                                                   PredictionsProviderABC)
from market_data_agg.providers.stocks import YFinanceProvider

__all__ = [
    # Core
    "MarketProviderABC",
    "ProviderErrorMapper",
    # Crypto
    "CoinGeckoProvider",
    # Stocks
    "YFinanceProvider",
    # Predictions
    "PredictionsProviderABC",
    "PolymarketProvider",
    # Core
    "provider_error_to_http",
    "raise_provider_http",
]
