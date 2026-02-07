"""Dependency injection for FastAPI.

Wiring of concrete implementations and injection into route handlers.
Providers are created in wire_providers(); routes depend on ABCs via Depends().
"""
from fastapi import FastAPI, Request

from market_data_agg.providers import (
    CoinGeckoProvider,
    MarketProviderABC,
    PolymarketProvider,
    PredictionsProviderABC,
    YFinanceProvider,
)


def wire_providers(app: FastAPI) -> None:
    """Create and attach shared provider instances to app.state (composition root).

    Call this from the app lifespan so implementations are wired once at startup.
    """
    app.state.stocks_provider = YFinanceProvider()
    app.state.crypto_provider = CoinGeckoProvider()
    app.state.predictions_provider = PolymarketProvider()


def get_stocks_provider(request: Request) -> MarketProviderABC:
    """Inject the shared stocks provider (abstraction)."""
    return request.app.state.stocks_provider


def get_crypto_provider(request: Request) -> MarketProviderABC:
    """Inject the shared crypto provider (abstraction)."""
    return request.app.state.crypto_provider


def get_predictions_provider(request: Request) -> PredictionsProviderABC:
    """Inject the shared predictions provider (abstraction)."""
    return request.app.state.predictions_provider
