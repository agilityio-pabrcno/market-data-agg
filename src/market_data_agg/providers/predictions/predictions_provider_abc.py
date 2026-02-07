"""Abstract base class for prediction/events market data providers."""
from abc import abstractmethod

from market_data_agg.providers.core import MarketProviderABC
from market_data_agg.schemas import MarketQuote


class PredictionsProviderABC(MarketProviderABC):
    """Base interface for prediction market data providers.

    Extends MarketProviderABC with prediction-specific functionality.
    Subclasses implement this to provide data from prediction markets.
    """

    @abstractmethod
    async def list_markets(
        self,
        active: bool = True,
        limit: int = 100,
        tag_id: str | None = None,
    ) -> list[MarketQuote]:
        """List available prediction markets.

        Args:
            active: Filter for active markets only.
            limit: Maximum number of markets to return.
            tag_id: Optional tag ID to filter by category.

        Returns:
            List of MarketQuotes for available markets.
        """
