"""Market data providers for stocks, crypto, and prediction markets.

This module provides a unified interface (MarketProvider) for fetching
market data from multiple sources:

- YFinanceProvider: Stock market data via Yahoo Finance
- CoinGeckoProvider: Cryptocurrency data via CoinGecko API
- PolymarketProvider: Prediction market data via Polymarket API

All providers implement the MarketProvider ABC and return unified
MarketQuote and StreamMessage objects.

Example:
    async with YFinanceProvider() as provider:
        quote = await provider.get_quote("AAPL")
        print(f"{quote.symbol}: ${quote.value}")

        async for msg in provider.stream(["AAPL", "MSFT"]):
            print(f"Update: {msg.symbol} = ${msg.price}")
"""
from market_data_agg.providers.base import MarketProvider
from market_data_agg.providers.coingecko import CoinGeckoProvider
from market_data_agg.providers.polymarket import PolymarketProvider
from market_data_agg.providers.yfinance import YFinanceProvider

__all__ = [
    "MarketProvider",
    "YFinanceProvider",
    "CoinGeckoProvider",
    "PolymarketProvider",
]
