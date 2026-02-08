"""FastAPI dependency injection: app.state holds singletons; Depends() resolves them.

No external DI container. Lifespan (main.py) creates providers and services once
and attaches them to app.state; these getters are used by Depends().
"""
from typing import Annotated

from fastapi import Depends, Request

from market_data_agg.services import MarketsService


def get_markets_service(request: Request) -> MarketsService:
    """Resolve MarketsService from app.state (created at startup)."""
    return request.app.state.markets_service


MarketsServiceDep = Annotated[MarketsService, Depends(get_markets_service)]
