# Router cURL tests and expected outputs

Start the server (from project root):

```bash
poetry run uvicorn market_data_agg.main:app --host 127.0.0.1 --port 8000
```

Base URL: `http://127.0.0.1:8000`

---

## Response schema (all quote endpoints)

`MarketQuote` is returned as JSON with:

| Field      | Type     | Description |
|-----------|----------|-------------|
| `source`  | string   | `"stock"`, `"crypto"`, or `"events"` (prediction markets) |
| `symbol`  | string   | Ticker (stocks/crypto) or market question (polymarket) |
| `value`   | number   | Price, or probability 0–1 for prediction markets |
| `volume`  | number?  | Trading volume |
| `timestamp` | string | ISO 8601 datetime |
| `metadata` | object? | Provider-specific (e.g. `change_24h`, `slug`, `provider`) |

---

## Health

```bash
curl -s http://127.0.0.1:8000/
```

**Expected:** `200`  
**Body:** `{"status":"ok"}`

---

## Stocks (`/stocks`)

| Endpoint | Method | Expected | Notes |
|----------|--------|----------|--------|
| `/stocks/overview` | GET | 200 | List of top stock quotes (e.g. AAPL, MSFT, GOOGL, AMZN, NVDA) |
| `/stocks/{symbol}` | GET | 200 / 404 | Single quote; use uppercase ticker (e.g. AAPL) |
| `/stocks/{symbol}/history?days=N` | GET | 200 | N days (1–365); invalid symbol can return `[]` (200) |
| `/stocks/refresh` | POST | 200 | `{"status":"refreshed"}` |

**Examples:**

```bash
curl -s http://127.0.0.1:8000/stocks/overview
curl -s http://127.0.0.1:8000/stocks/AAPL
curl -s "http://127.0.0.1:8000/stocks/AAPL/history?days=7"
curl -s -X POST http://127.0.0.1:8000/stocks/refresh
```

**Sample overview item:**

```json
{
  "source": "stock",
  "symbol": "AAPL",
  "value": 278.12,
  "volume": 50420700.0,
  "timestamp": "2026-02-07T02:59:59.870356",
  "metadata": {"provider": "yfinance"}
}
```

---

## Crypto (`/crypto`)

| Endpoint | Method | Expected | Notes |
|----------|--------|----------|--------|
| `/crypto/overview` | GET | 200 / 429 | Top coins; **429** when CoinGecko rate limit hit |
| `/crypto/{symbol}` | GET | 200 / 404 | CoinGecko id (e.g. `bitcoin`, `ethereum`) |
| `/crypto/{symbol}/history?days=N` | GET | 200 / 404 | N days (1–365) |
| `/crypto/refresh` | POST | 200 | `{"status":"refreshed"}` |

**Examples:**

```bash
curl -s http://127.0.0.1:8000/crypto/overview
curl -s http://127.0.0.1:8000/crypto/bitcoin
curl -s "http://127.0.0.1:8000/crypto/bitcoin/history?days=7"
curl -s http://127.0.0.1:8000/crypto/nonexistent   # 404
curl -s -X POST http://127.0.0.1:8000/crypto/refresh
```

**Sample quote:**

```json
{
  "source": "crypto",
  "symbol": "bitcoin",
  "value": 70319.0,
  "volume": 104197709897.0,
  "timestamp": "2026-02-07T00:00:08",
  "metadata": {"market_cap": 1404672703279.63, "change_24h": 8.51}
}
```

**404 response:** `{"detail":"Coin 'nonexistent' not found"}`

---

## Predictions (`/predictions`)

| Endpoint | Method | Expected | Notes |
|----------|--------|----------|--------|
| `/predictions/overview` | GET | 200 | Active prediction markets (default set) |
| `/predictions/markets` | GET | 200 | Query: `?active=true&limit=50&tag_id=...` |
| `/predictions/markets/{market_id}` | GET | 200 / 404 | `market_id` = slug or condition ID |
| `/predictions/refresh` | POST | 200 | `{"status":"refreshed"}` |

**Examples:**

```bash
curl -s http://127.0.0.1:8000/predictions/overview
curl -s "http://127.0.0.1:8000/predictions/markets?limit=5"
curl -s http://127.0.0.1:8000/predictions/markets/microstrategy-sell-any-bitcoin-in-2025
curl -s http://127.0.0.1:8000/predictions/markets/invalid-id   # 404
curl -s -X POST http://127.0.0.1:8000/predictions/refresh
```

**Sample market (source is `events`):**

```json
{
  "source": "events",
  "symbol": "MicroStrategy sells any Bitcoin in 2025?",
  "value": 1.0,
  "volume": 17976157.53,
  "timestamp": "2026-02-06T20:33:24.530284Z",
  "metadata": {
    "slug": "microstrategy-sell-any-bitcoin-in-2025",
    "top_outcome": "No",
    "condition_id": "0x19ee98e348c0ccb341d1b9566fa14521566e9b2ea7aed34dc407a0ec56be36a2",
    "clob_token_ids": ["...", "..."]
  }
}
```

**404 response:** `{"detail":"Market not found: invalid-id"}`

---

## Markets (aggregated)

| Endpoint | Method | Expected | Notes |
|----------|--------|----------|--------|
| `/markets/overview` | GET | 200 | Stocks + crypto + predictions; partial result if a provider fails |
| `/markets/top-movers` | GET | 200 | Query: `?source=stock\|crypto\|events&limit=10`; no `source` = all three |

**Examples:**

```bash
curl -s http://127.0.0.1:8000/markets/overview
curl -s "http://127.0.0.1:8000/markets/top-movers?limit=5"
curl -s "http://127.0.0.1:8000/markets/top-movers?source=stock&limit=3"
curl -s "http://127.0.0.1:8000/markets/top-movers?source=crypto&limit=3"
```

**Note:** If a provider fails (e.g. CoinGecko 429), its results are omitted and the rest are returned (partial 200). Using `?source=stock` or `?source=events` avoids crypto when rate-limited.

---

## Quick checklist

| Test | curl | Expected |
|------|------|----------|
| Health | `curl -s http://127.0.0.1:8000/` | `{"status":"ok"}`, 200 |
| Stocks overview | `curl -s http://127.0.0.1:8000/stocks/overview` | JSON array, 200 |
| Stock quote | `curl -s http://127.0.0.1:8000/stocks/AAPL` | One `MarketQuote`, 200 |
| Crypto quote | `curl -s http://127.0.0.1:8000/crypto/bitcoin` | One `MarketQuote`, 200 |
| Crypto 404 | `curl -s http://127.0.0.1:8000/crypto/nonexistent` | `{"detail":"..."}`, 404 |
| Predictions overview | `curl -s http://127.0.0.1:8000/predictions/overview` | JSON array, 200 |
| Predictions 404 | `curl -s http://127.0.0.1:8000/predictions/markets/invalid-id` | `{"detail":"..."}`, 404 |
| Markets (stocks only) | `curl -s "http://127.0.0.1:8000/markets/top-movers?source=stock&limit=2"` | JSON array, 200 |
| Refresh | `curl -s -X POST http://127.0.0.1:8000/stocks/refresh` | `{"status":"refreshed"}`, 200 |
