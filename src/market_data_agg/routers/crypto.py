"""Cryptocurrency market data routes (CoinGecko).

Quote/history/overview/refresh logic will live in a crypto service layer;
this router should only call the service and return responses.
"""
# TODO: Introduce a crypto service layer: move get_quote, get_history,
#       get_overview_quotes, and refresh handling there; keep this module as thin HTTP handlers.
# TODO: Add middleware for request logging, metrics, and correlation IDs.
# TODO: Add API gateway (rate limiting) in front of routers.
# TODO: Add auth (API keys, JWT, or OAuth) and protect sensitive/refresh endpoints.
# TODO: Improve error handling: central exception handler, structured error responses, retries.
import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from market_data_agg.dependencies import get_crypto_provider
from market_data_agg.providers import MarketProviderABC
from market_data_agg.schemas import MarketQuote

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crypto", tags=["crypto"])



@router.get("/overview", response_model=list[MarketQuote])
async def get_crypto_overview(
    provider: MarketProviderABC = Depends(get_crypto_provider),
) -> list[MarketQuote]:
    """Get overview (top by market cap) crypto quotes.

    Returns the provider's default set of top cryptocurrencies.
    """
    # TODO: Move calling provider.get_overview_quotes() and error handling to service layer.
    try:
        return await provider.get_overview_quotes()
    except httpx.HTTPStatusError as e:
        status = 502 if e.response.status_code >= 500 else e.response.status_code
        raise HTTPException(status_code=status, detail="CoinGecko API error") from e
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request to CoinGecko timed out")
    except Exception as exc:
        logger.exception("Failed to fetch crypto overview")
        raise HTTPException(status_code=500, detail="Failed to fetch overview") from exc


@router.get("/{symbol}", response_model=MarketQuote)
async def get_crypto_quote(
    symbol: str,
    provider: MarketProviderABC = Depends(get_crypto_provider),
) -> MarketQuote:
    """Get the current quote for a cryptocurrency.

    Args:
        symbol: CoinGecko ID (e.g., "bitcoin", "ethereum", "solana").
            See https://api.coingecko.com/api/v3/coins/list for all IDs.

    Returns:
        Current market quote with price and metadata.
    """
    # TODO: Move get_quote(symbol), normalization, and HTTP error mapping to service layer.
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
    provider: MarketProviderABC = Depends(get_crypto_provider),
) -> list[MarketQuote]:
    """Get historical data for a cryptocurrency.

    Args:
        symbol: CoinGecko ID.
        days: Number of days of history (default: 30, max: 365).

    Returns:
        List of historical quotes ordered by timestamp.
    """
    # TODO: Move date range (days → start/end), get_history(), and error mapping to service layer.
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
    provider: MarketProviderABC = Depends(get_crypto_provider),
) -> dict[str, str]:
    """Force refresh the crypto data provider.

    Clears any cached data.
    """
    # TODO: Move refresh orchestration and response shape to service layer.
    try:
        await provider.refresh()
        return {"status": "refreshed"}
    except Exception as exc:
        logger.exception("Failed to refresh CoinGecko provider")
        raise HTTPException(status_code=500, detail="Failed to refresh") from exc
