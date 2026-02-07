"""Abstract base class for cryptocurrency data providers."""
from market_data_agg.providers.core import MarketProviderABC


class CryptoProviderABC(MarketProviderABC):
    """Base interface for cryptocurrency market data providers.

    Extends MarketProviderABC with crypto-specific functionality.
    Subclasses implement this to provide data from crypto exchanges and APIs.
    """

    # Crypto providers inherit all methods from MarketProviderABC
    # Additional crypto-specific methods can be added here in the future
    # Examples:
    # - get_market_cap_rank()
    # - get_token_info()
    # - get_supply_data()
