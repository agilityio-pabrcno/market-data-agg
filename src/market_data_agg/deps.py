"""FastAPI dependency injection: app.state holds singletons; Depends() resolves them.

No external DI container. Lifespan (main.py) creates providers and services once
and attaches them to app.state; these getters are used by Depends().
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, WebSocket

from market_data_agg.services import MarketService, MarketsService


def get_stocks_service(request: Request) -> MarketService:
    """Resolve stocks MarketService from app.state (created at startup)."""
    return request.app.state.stocks_service


def get_crypto_service(request: Request) -> MarketService:
    """Resolve crypto MarketService from app.state."""
    return request.app.state.crypto_service


def get_markets_service(request: Request) -> MarketsService:
    """Resolve aggregated MarketsService from app.state."""
    return request.app.state.markets_service


def get_prediction_service(request: Request, provider: str) -> MarketService:
    """Resolve prediction MarketService by provider name (e.g. 'polymarket')."""
    services = request.app.state.prediction_services
    if provider not in services:
        raise HTTPException(
            404,
            detail=f"Unknown prediction provider: {provider}. Available: {', '.join(services)}",
        )
    return services[provider]


def get_prediction_service_ws(websocket: WebSocket, provider: str) -> MarketService:
    """Resolve prediction MarketService for WebSocket (provider from path)."""
    app = websocket.scope["app"]
    services = app.state.prediction_services
    if provider not in services:
        raise HTTPException(
            404,
            detail=f"Unknown prediction provider: {provider}. Available: {', '.join(services)}",
        )
    return services[provider]


def get_polymarket_service_ws(websocket: WebSocket) -> MarketService:
    """Default prediction provider for /predictions/stream (no provider in path)."""
    return get_prediction_service_ws(websocket, "polymarket")


# Type aliases for route injection
StocksService = Annotated[MarketService, Depends(get_stocks_service)]
CryptoService = Annotated[MarketService, Depends(get_crypto_service)]
MarketsServiceDep = Annotated[MarketsService, Depends(get_markets_service)]
PredictionService = Annotated[MarketService, Depends(get_prediction_service)]
PredictionServiceWs = Annotated[MarketService, Depends(get_prediction_service_ws)]
PolymarketServiceWs = Annotated[MarketService, Depends(get_polymarket_service_ws)]
