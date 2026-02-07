"""Main module for the market data aggregation service."""
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from market_data_agg.dependencies import wire_providers
from market_data_agg.routers import (crypto_router, markets_router,
                                     predictions_router, stocks_router)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Wire shared dependencies at startup; dispose on shutdown."""
    wire_providers(fastapi_app)
    yield
    # Optional: close any client resources on shutdown


app = FastAPI(
    title="Market Data Aggregator",
    description="Unified API for stocks, crypto, and prediction markets",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(stocks_router)
app.include_router(crypto_router)
app.include_router(predictions_router)
app.include_router(markets_router)



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
