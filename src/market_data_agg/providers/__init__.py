"""Market data providers for stocks, crypto, and prediction markets.
"""
from market_data_agg.providers.core import MarketProviderABC
from market_data_agg.providers.crypto import (CoinGeckoProvider,
                                              CryptoProviderABC)
from market_data_agg.providers.predictions import (PredictionsProviderABC,
                                              PolymarketProvider)
from market_data_agg.providers.stocks import (StocksProviderABC,
                                              YFinanceProvider)

__all__ = [
    # Core
    "MarketProviderABC",
    # Crypto
    "CryptoProviderABC",
    "CoinGeckoProvider",
    # Stocks
    "StocksProviderABC",
    "YFinanceProvider",
    # Predictions
    "PredictionsProviderABC",
    "PolymarketProvider",
]
