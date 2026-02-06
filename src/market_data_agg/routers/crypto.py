"""Cryptocurrency market data routes (CoinGecko)."""
# TODO: Move business logic (provider calls, mapping) into a crypto service layer.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO: Add API gateway (rate limiting) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive/refresh endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
import asyncio
import logging
from datetime import datetime, timedelta
from functools import lru_cache

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from market_data_agg.providers import CoinGeckoProvider
from market_data_agg.schemas import MarketQuote

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crypto", tags=["crypto"])


@lru_cache
def get_provider() -> CoinGeckoProvider:
    """Get singleton CoinGecko provider instance."""
    return CoinGeckoProvider()


@router.get("/{symbol}", response_model=MarketQuote)
async def get_crypto_quote(
    symbol: str,
    provider: CoinGeckoProvider = Depends(get_provider),
) -> MarketQuote:
    """Get the current quote for a cryptocurrency.

    Args:
        symbol: CoinGecko ID (e.g., "bitcoin", "ethereum", "solana").
            See https://api.coingecko.com/api/v3/coins/list for all IDs.

    Returns:
        Current market quote with price and metadata.
    """
    try:
        return await provider.get_quote(symbol)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found") from e
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"Request to CoinGecko timed out for '{symbol}'") from exc
    except Exception as exc:
        logger.exception("Failed to fetch crypto quote for %s", symbol)
        raise HTTPException(status_code=500, detail="Failed to fetch quote") from exc

@router.get("/{symbol}/history", response_model=list[MarketQuote])
async def get_crypto_history(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    provider: CoinGeckoProvider = Depends(get_provider),
) -> list[MarketQuote]:
    """Get historical data for a cryptocurrency.

    Args:
        symbol: CoinGecko ID.
        days: Number of days of history (default: 30, max: 365).

    Returns:
        List of historical quotes ordered by timestamp.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    try:
        return await provider.get_history(symbol, start, end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"History for '{symbol}' not found")
        status = 502 if e.response.status_code >= 500 else e.response.status_code
        raise HTTPException(status_code=status, detail="CoinGecko API error")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request to CoinGecko timed out")
    except Exception as exc:
        logger.exception("Failed to fetch crypto history for %s", symbol)
        raise HTTPException(status_code=500, detail="Failed to fetch history") from exc


@router.post("/refresh")
async def refresh_crypto(
    provider: CoinGeckoProvider = Depends(get_provider),
) -> dict[str, str]:
    """Force refresh the crypto data provider.

    Clears any cached data.
    """
    try:
        await provider.refresh()
        return {"status": "refreshed"}
    except Exception as exc:
        logger.exception("Failed to refresh CoinGecko provider")
        raise HTTPException(status_code=500, detail="Failed to refresh") from exc
