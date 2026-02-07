"""Prediction market routes (Polymarket provider).

List/get/overview/refresh logic will live in a predictions service layer;
this router should only call the service and return responses.
"""
# TODO: Introduce a predictions service layer: move list_markets,
#       get_quote, get_overview_quotes, and refresh handling there; keep this module as thin HTTP handlers.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO:  API gateway (rate limiting, routing) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive/refresh endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
import asyncio
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from market_data_agg.dependencies import get_predictions_provider
from market_data_agg.providers import PredictionsProviderABC
from market_data_agg.schemas import MarketQuote

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["predictions"])

# Route order: /overview before /markets so the overview endpoint is matched first.


@router.get("/overview", response_model=list[MarketQuote])
async def get_predictions_overview(
    provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> list[MarketQuote]:
    """Get overview (active) prediction markets.

    Returns the provider's default set of active markets for summary views.
    """
    # TODO: Service layer will own: calling provider.get_overview_quotes() and error handling.
    try:
        return await provider.get_overview_quotes()
    except httpx.HTTPStatusError as e:
        status = 502 if e.response.status_code >= 500 else e.response.status_code
        raise HTTPException(status_code=status, detail="Predictions API error") from e
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request to predictions API timed out")
    except Exception as exc:
        logger.exception("Failed to fetch predictions overview")
        raise HTTPException(status_code=500, detail="Failed to fetch overview") from exc


@router.get("/markets", response_model=list[MarketQuote])
async def list_markets(
    active: bool = Query(default=True, description="Filter for active markets only"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum markets to return"),
    tag_id: str | None = Query(default=None, description="Filter by tag/category ID"),
    provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> list[MarketQuote]:
    """List available prediction markets.

    Args:
        active: Filter for active (tradeable) markets only.
        limit: Maximum number of markets to return.
        tag_id: Optional category filter (e.g., crypto, politics, sports).

    Returns:
        List of prediction markets as MarketQuotes.
    """
    # TODO: Service layer will own: list_markets(active, limit, tag_id) and error mapping.
    try:
        return await provider.list_markets(active=active, limit=limit, tag_id=tag_id)
    except httpx.HTTPStatusError as e:
        status = 502 if e.response.status_code >= 500 else e.response.status_code
        raise HTTPException(status_code=status, detail="Predictions API error")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request to predictions API timed out")
    except Exception as exc:
        logger.exception("Failed to fetch predictions markets")
        raise HTTPException(status_code=500, detail="Failed to fetch markets") from exc


@router.get("/markets/{market_id}", response_model=MarketQuote)
async def get_market(
    market_id: str,
    provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> MarketQuote:
    """Get details for a specific prediction market.

    Args:
        market_id: Market slug (e.g., "will-bitcoin-reach-100k") or condition ID.

    Returns:
        Market quote with probability and metadata.
    """
    # TODO: Service layer will own: get_quote(market_id) and 404/5xx mapping.
    try:
        return await provider.get_quote(market_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Market '{market_id}' not found")
        status = 502 if e.response.status_code >= 500 else e.response.status_code
        raise HTTPException(status_code=status, detail="Predictions API error")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request to predictions API timed out")
    except Exception as exc:
        logger.exception("Failed to fetch predictions market %s", market_id)
        raise HTTPException(status_code=500, detail="Failed to fetch market") from exc


@router.post("/refresh")
async def refresh_predictions(
    provider: PredictionsProviderABC = Depends(get_predictions_provider),
) -> dict[str, str]:
    """Force refresh the predictions provider.

    Clears cached market data and reconnects WebSocket.
    """
    # TODO: Service layer will own: refresh orchestration and response shape.
    try:
        await provider.refresh()
        return {"status": "refreshed"}
    except Exception as exc:
        logger.exception("Failed to refresh predictions provider")
        raise HTTPException(status_code=500, detail="Failed to refresh") from exc
