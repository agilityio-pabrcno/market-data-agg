"""API routers for market data endpoints.

Includes routes for:
- /stocks - Stock market data (Alpaca)
- /crypto - Cryptocurrency data (CoinGecko)
- /polymarket - Prediction markets (Polymarket)
- /markets - Aggregated views across all sources
- /ws/stream - WebSocket real-time stream
"""
from market_data_agg.routers.crypto import router as crypto_router
from market_data_agg.routers.markets import router as markets_router
from market_data_agg.routers.polymarket import router as polymarket_router
from market_data_agg.routers.stocks import router as stocks_router

__all__ = [
    "stocks_router",
    "crypto_router",
    "polymarket_router",
    "markets_router",
]
