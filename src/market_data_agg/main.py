"""Main module for the market data aggregation service."""
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from market_data_agg.providers import (CoinGeckoProvider, PolymarketProvider,
                                       YFinanceProvider)
from market_data_agg.routers import (crypto_router, markets_router,
                                    predictions_router, stocks_router)
from market_data_agg.services import MarketService, MarketsService
from market_data_agg.services.market_factory import create_market_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Create providers and services at startup; close providers on shutdown."""
    # Providers (singletons)
    stocks_provider = YFinanceProvider(poll_interval=15.0)
    crypto_provider = CoinGeckoProvider()
    polymarket_provider = PolymarketProvider(poll_interval_seconds=60.0)

    # Per-domain services
    stocks_service = create_market_service(
        stocks_provider, "Stock", "Stocks API", symbol_normalizer=str.upper
    )
    crypto_service = create_market_service(
        crypto_provider, "Crypto", "CoinGecko", symbol_normalizer=str.lower
    )
    polymarket_service = create_market_service(
        polymarket_provider, "Market", "Polymarket"
    )

    prediction_services: dict[str, MarketService] = {"polymarket": polymarket_service}
    markets_service = MarketsService(
        stocks_provider=stocks_provider,
        crypto_provider=crypto_provider,
        prediction_providers=[("polymarket", polymarket_provider)],
    )

    fastapi_app.state.stocks_service = stocks_service
    fastapi_app.state.crypto_service = crypto_service
    fastapi_app.state.markets_service = markets_service
    fastapi_app.state.prediction_services = prediction_services

    # Keep provider refs for clean shutdown
    fastapi_app.state.providers_to_close = [
        stocks_provider,
        crypto_provider,
        polymarket_provider,
    ]

    yield

    # Close provider resources (e.g. httpx clients)
    for provider in fastapi_app.state.providers_to_close:
        try:
            await provider.close()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Error closing provider %s: %s", type(provider).__name__, exc)


app = FastAPI(
    title="Market Data Aggregator",
    description="Unified API for stocks, crypto, and prediction markets",
    version="0.1.0",
    lifespan=lifespan,
)

# TODO: Add middlewares for API gateway (auth, request ID, CORS).
# TODO: Add rate limiting middleware (e.g. slowapi or custom per-route limits).

# Include routers
app.include_router(stocks_router)
app.include_router(crypto_router)
app.include_router(predictions_router)
app.include_router(markets_router)



@app.get("/")
def health():
    """Return health check status."""
    return {"status": "ok"}

def run():
    """Run the server (uvicorn). Use for `poetry run start`."""
    uvicorn.run("market_data_agg.main:app", host="127.0.0.1", port=8001)


def run_dev():
    """Run the development server with Postgres running via Docker."""
    project_root = Path(__file__).resolve().parent.parent.parent
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "postgres"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("Failed to start Postgres:", e.stderr or e.stdout, file=sys.stderr)
        sys.exit(1)
    uvicorn.run("market_data_agg.main:app", host="0.0.0.0", port=8000, reload=True)
