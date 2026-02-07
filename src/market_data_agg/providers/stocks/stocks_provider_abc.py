"""Abstract base class for stock market data providers."""
from market_data_agg.providers.core import MarketProviderABC


class StocksProviderABC(MarketProviderABC):
    """Base interface for stock market data providers.

    Extends MarketProviderABC with stock-specific functionality.
    Subclasses implement this to provide data from stock exchanges and APIs.
    """

    # Stock providers inherit all methods from MarketProviderABC
    # Additional stock-specific methods can be added here in the future
    # Examples:
    # - get_fundamentals()
    # - get_dividends()
    # - get_earnings()
