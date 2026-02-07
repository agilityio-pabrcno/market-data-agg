"""Market data providers for stocks, crypto, and prediction markets.
"""
from market_data_agg.providers.core import MarketProviderABC
from market_data_agg.providers.crypto import CoinGeckoProvider
from market_data_agg.providers.predictions import (PredictionsProviderABC,
                                              PolymarketProvider)
from market_data_agg.providers.stocks import YFinanceProvider

__all__ = [
    # Core
    "MarketProviderABC",
    # Crypto
    "CoinGeckoProvider",
    # Stocks
    "YFinanceProvider",
    # Predictions
    "PredictionsProviderABC",
    "PolymarketProvider",
]
