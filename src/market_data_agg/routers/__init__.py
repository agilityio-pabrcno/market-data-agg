"""API routers for market data endpoints.

Includes routes for:
- /stocks - Stock market data (Yahoo Finance)
- /crypto - Cryptocurrency data (CoinGecko)
- /predictions - Prediction markets (Polymarket)
- /markets - Aggregated views across all sources
- /stocks/stream, /crypto/stream, /predictions/stream - WebSocket real-time streams (per provider)

TODO: Add middleware (e.g. request ID, CORS, API gateway).
TODO: Add rate limiting (per-route or global, e.g. slowapi or custom).
TODO: Add auth (e.g. JWT, API key) and optional per-route protection.
"""
from market_data_agg.routers.crypto import router as crypto_router
from market_data_agg.routers.markets import router as markets_router
from market_data_agg.routers.predictions import router as predictions_router
from market_data_agg.routers.stocks import router as stocks_router

__all__ = [
    "stocks_router",
    "crypto_router",
    "predictions_router",
    "markets_router",
]
