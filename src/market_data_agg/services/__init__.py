"""Service layer: provider orchestration and exception-to-HTTP mapping.

TODO: Add better error handling (e.g. retries, circuit breaker, typed exceptions).
TODO: Add structured logging (request/response, latency, provider errors).
"""
from market_data_agg.services.crypto import CryptoService
from market_data_agg.services.markets import MarketsService
from market_data_agg.services.predictions import PredictionsService
from market_data_agg.services.stocks import StocksService

__all__ = [
    "CryptoService",
    "MarketsService",
    "PredictionsService",
    "StocksService",
]
