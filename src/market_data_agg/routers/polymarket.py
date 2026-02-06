"""Polymarket prediction market routes."""
# TODO: Move business logic (provider calls, mapping) into a polymarket service layer.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO: Consider API gateway (rate limiting, routing) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive/refresh endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
import asyncio
import logging
from functools import lru_cache

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from market_data_agg.providers import PolymarketProvider
from market_data_agg.schemas import MarketQuote

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/polymarket", tags=["polymarket"])


@lru_cache
def get_provider() -> PolymarketProvider:
    """Get singleton Polymarket provider instance."""
    return PolymarketProvider()


@router.get("/markets", response_model=list[MarketQuote])
async def list_markets(
    active: bool = Query(default=True, description="Filter for active markets only"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum markets to return"),
    tag_id: str | None = Query(default=None, description="Filter by tag/category ID"),
    provider: PolymarketProvider = Depends(get_provider),
) -> list[MarketQuote]:
    """List available prediction markets.

    Args:
        active: Filter for active (tradeable) markets only.
        limit: Maximum number of markets to return.
        tag_id: Optional category filter (e.g., crypto, politics, sports).

    Returns:
        List of prediction markets as MarketQuotes.
    """
    try:
        return await provider.list_markets(active=active, limit=limit, tag_id=tag_id)
    except httpx.HTTPStatusError as e:
        status = 502 if e.response.status_code >= 500 else e.response.status_code
        raise HTTPException(status_code=status, detail="Polymarket API error")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request to Polymarket timed out")
    except Exception as exc:
        logger.exception("Failed to fetch Polymarket markets")
        raise HTTPException(status_code=500, detail="Failed to fetch markets") from exc


@router.get("/markets/{market_id}", response_model=MarketQuote)
async def get_market(
    market_id: str,
    provider: PolymarketProvider = Depends(get_provider),
) -> MarketQuote:
    """Get details for a specific prediction market.

    Args:
        market_id: Market slug (e.g., "will-bitcoin-reach-100k") or condition ID.

    Returns:
        Market quote with probability and metadata.
    """
    try:
        return await provider.get_quote(market_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Market '{market_id}' not found")
        status = 502 if e.response.status_code >= 500 else e.response.status_code
        raise HTTPException(status_code=status, detail="Polymarket API error")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request to Polymarket timed out")
    except Exception as exc:
        logger.exception("Failed to fetch Polymarket market %s", market_id)
        raise HTTPException(status_code=500, detail="Failed to fetch market") from exc


@router.post("/refresh")
async def refresh_polymarket(
    provider: PolymarketProvider = Depends(get_provider),
) -> dict[str, str]:
    """Force refresh the Polymarket provider.

    Clears cached market data and reconnects WebSocket.
    """
    try:
        await provider.refresh()
        return {"status": "refreshed"}
    except Exception as exc:
        logger.exception("Failed to refresh Polymarket provider")
        raise HTTPException(status_code=500, detail="Failed to refresh") from exc
