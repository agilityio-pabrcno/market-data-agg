"""Mapping from Polymarket API responses to MarketQuote."""
import json
from datetime import datetime
from typing import Any

from market_data_agg.db import Source
from market_data_agg.providers.polymarket.models import PolymarketQuoteMetadata
from market_data_agg.schemas import MarketQuote


def parse_outcome_prices(market: dict[str, Any]) -> list[float]:
    """Parse outcome prices from market data.

    Polymarket stores outcomePrices as a JSON string like '["0.65","0.35"]'.

    Args:
        market: Raw market data from Gamma API.

    Returns:
        List of probabilities per outcome.
    """
    prices_str = market.get("outcomePrices", "[]")
    if isinstance(prices_str, str):
        prices = json.loads(prices_str)
    else:
        prices = prices_str

    return [float(p) for p in prices]


def parse_outcomes(market: dict[str, Any]) -> list[str]:
    """Parse outcome labels from market data.

    Args:
        market: Raw market data from Gamma API.

    Returns:
        List of outcome labels (e.g. ['Yes', 'No']).
    """
    outcomes_str = market.get("outcomes", "[]")
    if isinstance(outcomes_str, str):
        return json.loads(outcomes_str)
    return outcomes_str


def market_to_quote(
    market: dict[str, Any],
    outcome_index: int = 0,
) -> MarketQuote:
    """Convert Polymarket market data to a MarketQuote.

    Args:
        market: Raw market data from Gamma API.
        outcome_index: Which outcome to use (0 = first, usually "Yes").

    Returns:
        MarketQuote with probability (0-1) as value.
    """
    prices = parse_outcome_prices(market)
    outcomes = parse_outcomes(market)
    slug = market.get("slug", market.get("conditionId", "unknown"))

    value = prices[outcome_index] if outcome_index < len(prices) else 0.0

    updated_at = market.get("updatedAt")
    if updated_at:
        try:
            timestamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.utcnow()
    else:
        timestamp = datetime.utcnow()

    volume_str = market.get("volume")
    volume = float(volume_str) if volume_str else None

    metadata = PolymarketQuoteMetadata(
        question=market.get("question"),
        outcomes=outcomes,
        outcome_prices=prices,
        condition_id=market.get("conditionId"),
        clob_token_ids=market.get("clobTokenIds", []),
        outcome_index=outcome_index,
        outcome=outcomes[outcome_index] if outcome_index < len(outcomes) else None,
    )

    return MarketQuote(
        source=Source.POLYMARKET,
        symbol=slug,
        value=value,
        volume=volume,
        timestamp=timestamp,
        metadata=metadata.to_metadata_dict(),
    )
