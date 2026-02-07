"""DI container. Wire via init_container(); endpoints use Depends(Provide[Container.*])."""
from typing import Annotated

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide
from fastapi import Depends, HTTPException, Request, WebSocket

from market_data_agg.providers import (CoinGeckoProvider, PolymarketProvider,
                                       YFinanceProvider)
from market_data_agg.services import MarketService, MarketsService
from market_data_agg.services.market_factory import create_market_service


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "market_data_agg.routers.stocks",
            "market_data_agg.routers.crypto",
            "market_data_agg.routers.predictions",
            "market_data_agg.routers.markets",
        ]
    )

    stocks_provider = providers.Singleton(YFinanceProvider, poll_interval=15.0)
    crypto_provider = providers.Singleton(CoinGeckoProvider)

    polymarket_provider = providers.Singleton(
        PolymarketProvider, poll_interval_seconds=60.0
    )

    stocks_service = providers.Singleton(
        create_market_service,
        stocks_provider,
        "Stock",
        "Stocks API",
        symbol_normalizer=str.upper,
    )
    crypto_service = providers.Singleton(
        create_market_service,
        crypto_provider,
        "Crypto",
        "CoinGecko",
        symbol_normalizer=str.lower,
    )

    polymarket_service = providers.Singleton(
        create_market_service,
        polymarket_provider,
        "Market",
        "Polymarket",
    )
    prediction_services = providers.Dict(polymarket=polymarket_service)

    prediction_providers_list = providers.Callable(
        lambda p: [("polymarket", p)], polymarket_provider
    )
    markets_service = providers.Singleton(
        MarketsService,
        stocks_provider=stocks_provider,
        crypto_provider=crypto_provider,
        prediction_providers=prediction_providers_list,
    )


# Type aliases for route injection (avoid repeating Annotated[...] in every route)
StocksService = Annotated[MarketService, Depends(Provide[Container.stocks_service])]
CryptoService = Annotated[MarketService, Depends(Provide[Container.crypto_service])]
MarketsServiceDep = Annotated[MarketsService, Depends(Provide[Container.markets_service])]


def init_container() -> Container:
    """Create container and wire to router modules."""
    container = Container()
    container.wire()
    return container


def _prediction_service(container: Container, provider: str) -> MarketService:
    services = container.prediction_services()
    if provider not in services:
        raise HTTPException(
            404,
            detail=f"Unknown prediction provider: {provider}. Available: {', '.join(services)}",
        )
    return services[provider]


def get_prediction_service(request: Request, provider: str) -> MarketService:
    return _prediction_service(request.app.state.container, provider)


def get_prediction_service_ws(websocket: WebSocket, provider: str) -> MarketService:
    return _prediction_service(websocket.scope["app"].state.container, provider)


def get_polymarket_service_ws(websocket: WebSocket) -> MarketService:
    """Default prediction provider for /predictions/stream (no provider in path)."""
    return _prediction_service(websocket.scope["app"].state.container, "polymarket")


# Type aliases for prediction routes (depend on path param `provider`; define after get_prediction_*)
PredictionService = Annotated[MarketService, Depends(get_prediction_service)]
PredictionServiceWs = Annotated[MarketService, Depends(get_prediction_service_ws)]
PolymarketServiceWs = Annotated[MarketService, Depends(get_polymarket_service_ws)]
