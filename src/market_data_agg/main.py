"""Main module for the market data aggregation service."""
import subprocess
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from market_data_agg.routers import (
    crypto_router,
    markets_router,
    polymarket_router,
    stream_router,
    stocks_router,
)

app = FastAPI(
    title="Market Data Aggregator",
    description="Unified API for stocks, crypto, and prediction markets",
    version="0.1.0",
)

# Include routers
app.include_router(stocks_router)
app.include_router(crypto_router)
app.include_router(polymarket_router)
app.include_router(markets_router)
app.include_router(stream_router)


@app.get("/")
def health():
    """Return health check status."""
    return {"status": "ok"}

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
