# Manual cURL tests

Start the server (project root):

```bash
poetry run uvicorn market_data_agg.main:app --host 127.0.0.1 --port 8000
```

Base URL: **http://127.0.0.1:8000**

---

## Health

```bash
curl -s http://127.0.0.1:8000/
```

---

## Stocks

```bash
# Overview (top stocks)
curl -s http://127.0.0.1:8000/stocks/overview

# Single quote (use ticker e.g. AAPL, MSFT)
curl -s http://127.0.0.1:8000/stocks/AAPL

# History (days 1–365)
curl -s "http://127.0.0.1:8000/stocks/AAPL/history?days=7"

# Refresh
curl -s -X POST http://127.0.0.1:8000/stocks/refresh
```

---

## Crypto

```bash
# Overview (top coins)
curl -s http://127.0.0.1:8000/crypto/overview

# Single quote (CoinGecko id: bitcoin, ethereum, solana, …)
curl -s http://127.0.0.1:8000/crypto/bitcoin

# History (days 1–365)
curl -s "http://127.0.0.1:8000/crypto/bitcoin/history?days=7"

# Not found (expect 404)
curl -s http://127.0.0.1:8000/crypto/nonexistent

# Refresh
curl -s -X POST http://127.0.0.1:8000/crypto/refresh
```

---

## Predictions

```bash
# Overview (active prediction markets)
curl -s http://127.0.0.1:8000/predictions/overview

# List markets (optional: ?active=true&limit=50&tag_id=…)
curl -s "http://127.0.0.1:8000/predictions/markets?limit=10"

# Single market by slug or condition id
curl -s http://127.0.0.1:8000/predictions/markets/microstrategy-sell-any-bitcoin-in-2025

# Not found (expect 404)
curl -s http://127.0.0.1:8000/predictions/markets/invalid-id

# Refresh
curl -s -X POST http://127.0.0.1:8000/predictions/refresh
```

---

## Markets (aggregated)

```bash
# Overview (stocks + crypto + predictions)
curl -s http://127.0.0.1:8000/markets/overview

# Top movers (optional: ?source=stock|crypto|events&limit=10)
curl -s "http://127.0.0.1:8000/markets/top-movers?limit=10"
curl -s "http://127.0.0.1:8000/markets/top-movers?source=stock&limit=5"
curl -s "http://127.0.0.1:8000/markets/top-movers?source=crypto&limit=5"
```

---

## Stream (WebSocket)

Stream endpoints use each provider’s `stream()` and send `MarketQuote` JSON messages. Pass symbols in the query string.

**Stocks** (polling):

```bash
# Install wscat: npm i -g wscat
wscat -c "ws://127.0.0.1:8000/stocks/stream?symbols=AAPL,MSFT"
```

**Crypto** (polling):

```bash
wscat -c "ws://127.0.0.1:8000/crypto/stream?symbols=bitcoin,ethereum"
```

**Predictions** (Polymarket CLOB WebSocket):

```bash
wscat -c "ws://127.0.0.1:8000/predictions/stream?symbols=microstrategy-sell-any-bitcoin-in-2025"
```

Each message is a JSON object: `source`, `symbol`, `value`, `volume`, `timestamp`, `metadata`.

---

## With status code (optional)

Append `-w "\nHTTP %{http_code}\n"` to see the response status:

```bash
curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/
curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/stocks/AAPL
```

Pretty-print JSON (if you have `jq`):

```bash
curl -s http://127.0.0.1:8000/stocks/AAPL | jq .
```
