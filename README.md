# Market Data Aggregator API — Technical Design

## Purpose

Design and implement a **production-style Python backend** that aggregates real-time and historical data from:

* Stocks (Alpaca or similar provider)
* Crypto (CoinGecko / CCXT)
* Prediction Markets (Polymarket)

The system exposes a unified interface through:

* REST API
* Real-time WebSocket streaming
* Token-based authentication
* Caching layer
* Persistent storage
* Background refresh jobs

The goal is to follow **modern backend engineering practices** with strong typing, modularity, and scalability.

---

## Tech Stack

| Layer           | Technology  | Purpose                            |
| --------------- | ----------- | ---------------------------------- |
| API             | FastAPI     | REST + WebSockets + OpenAPI        |
| Validation      | Pydantic    | typed schemas + runtime validation |
| ORM             | SQLModel    | DB models + Pydantic integration   |
| Dependency Mgmt | Poetry      | reproducible environments          |
| Database        | PostgreSQL  | persistent storage                 |
| Cache           | Redis       | low-latency cache + pub/sub        |
| HTTP Client     | httpx       | async external API calls           |
| Background Jobs | Celery / RQ | periodic refresh tasks             |
| Auth            | JWT         | stateless token authentication     |

---

## High-Level Architecture

```
Clients
   ↓
FastAPI (API Gateway)
   ↓
Services Layer (business logic)
   ↓
Providers (Alpaca / Crypto / Polymarket)
   ↓
Redis (cache + pub/sub)
   ↓
PostgreSQL
```

Responsibilities:

* Providers → external integrations
* Services → business logic
* Routers → transport/API layer
* Redis → caching + real-time broadcasting
* DB → persistence & history

---

## Project Structure

```
app/
  core/        config, security, cache
  db/          models, sessions
  providers/   external API clients
  services/    aggregation logic
  routers/     REST + WebSocket endpoints
  tasks/       background jobs
  main.py
```

Clear separation of concerns improves maintainability and testability.

---

## Data Model Strategy

### Unified Quote Model

All asset types share the same schema for simplified storage and querying.

```python
class MarketQuote(SQLModel, table=True):
    id: int | None
    source: str        # stock | crypto | polymarket
    symbol: str
    price: float
    volume: float | None
    timestamp: datetime
```

Benefits:

* consistent structure across providers
* easier aggregation and analytics
* simplified API responses

---

## Authentication

JWT Bearer tokens.

Flow:

```
POST /auth/login → returns token
Authorization: Bearer <token>
```

Optional roles:

* user
* admin

---

## REST API (Core Endpoints)

### Auth

```
POST /auth/register
POST /auth/login
POST /auth/refresh
```

### Stocks

```
GET /stocks/{symbol}
GET /stocks/{symbol}/history
GET /stocks/trending
POST /stocks/refresh
```

### Crypto

```
GET /crypto/{symbol}
GET /crypto/{symbol}/history
POST /crypto/refresh
```

### Predictions

```
GET /predictions/overview
GET /predictions/markets
GET /predictions/markets/{id}
POST /predictions/refresh
```

### Aggregated Views

```
GET /markets/overview
GET /markets/trends
GET /markets/top-movers
```

### User Features

```
GET/POST /watchlist
POST /alerts
POST /refresh/all
```

---

## Real-Time Streaming

Single WebSocket endpoint:

```
/ws/stream
```

Client subscription:

```json
{
  "subscribe": [
    {"type": "stock", "symbol": "AAPL"},
    {"type": "crypto", "symbol": "BTC"},
    {"type": "predictions", "symbol": "event-id"}
  ]
}
```

Server push message:

```json
{
  "source": "crypto",
  "symbol": "BTC",
  "price": 65200,
  "timestamp": 1700000000
}
```

Flow:

```
Providers → Redis Pub/Sub → WebSocket broadcast
```

---

## Caching Strategy

Redis TTL-based cache to reduce latency and external API usage.

Typical values:

* quotes: 10–30 seconds
* market lists: 5–10 minutes
* historical: longer-term

Benefits:

* faster responses
* fewer rate-limit issues
* lower operational cost

---

## Background Jobs

Scheduled tasks:

* fetch latest prices
* store historical snapshots
* compute trends
* evaluate alerts

Tooling: Celery or RQ.

---

## Database migrations

Schema changes are managed with **Alembic**. Use the same `DATABASE_URL` as the app (e.g. from `.env` or `.env.local`).

```bash
# Create a new migration after changing models in db/models.py
poetry run db-generate -m "Description of change"
# or: poetry run alembic revision --autogenerate -m "Description of change"

# Apply all pending migrations
poetry run db-migrate
# or: poetry run alembic upgrade head

# Roll back one revision
poetry run alembic downgrade -1
```

Run these from the project root so that `market_data_agg` is importable (Alembic is configured with `prepend_sys_path = src`).

---

## Dependency Management

Using Poetry:

```
poetry install
poetry run uvicorn market_data_agg.main:app --host 127.0.0.1 --port 8000
```

Advantages:

* lockfile-based reproducibility
* isolated environments
* simplified deployment

---

## Testing the API

Start the server (from project root):

```bash
poetry run uvicorn market_data_agg.main:app --host 127.0.0.1 --port 8000
```

Base URL: **http://127.0.0.1:8000**

### Health

```bash
curl -s http://127.0.0.1:8000/
# → {"status":"ok"}
```

### REST (curl)

**Stocks**

```bash
curl -s http://127.0.0.1:8000/stocks/overview
curl -s http://127.0.0.1:8000/stocks/AAPL
curl -s "http://127.0.0.1:8000/stocks/AAPL/history?days=7"
curl -s -X POST http://127.0.0.1:8000/stocks/refresh
```

**Crypto**

```bash
curl -s http://127.0.0.1:8000/crypto/overview
curl -s http://127.0.0.1:8000/crypto/bitcoin
curl -s "http://127.0.0.1:8000/crypto/bitcoin/history?days=7"
curl -s -X POST http://127.0.0.1:8000/crypto/refresh
```

**Predictions**

```bash
curl -s http://127.0.0.1:8000/predictions/overview
curl -s "http://127.0.0.1:8000/predictions/markets?limit=10"
curl -s http://127.0.0.1:8000/predictions/markets/microstrategy-sell-any-bitcoin-in-2025
curl -s -X POST http://127.0.0.1:8000/predictions/refresh
```

**Markets (aggregated)**

```bash
curl -s http://127.0.0.1:8000/markets/overview
curl -s "http://127.0.0.1:8000/markets/top-movers?limit=10"
curl -s "http://127.0.0.1:8000/markets/top-movers?source=stock&limit=5"
```

### WebSocket streams

Per-provider streams; pass symbols in the query string. Each message is a `MarketQuote` JSON.

```bash
# Install wscat: npm i -g wscat

# Stocks (polling)
wscat -c "ws://127.0.0.1:8000/stocks/stream?symbols=AAPL,MSFT"

# Crypto (polling)
wscat -c "ws://127.0.0.1:8000/crypto/stream?symbols=bitcoin,ethereum"

# Predictions (Polymarket CLOB)
wscat -c "ws://127.0.0.1:8000/predictions/stream?symbols=microstrategy-sell-any-bitcoin-in-2025"
```

### Optional

Show HTTP status: `curl -s -w "\nHTTP %{http_code}\n" http://127.0.0.1:8000/stocks/AAPL`  
Pretty-print JSON: `curl -s http://127.0.0.1:8000/stocks/AAPL | jq .`

More detail: see **docs/CURL_MANUAL_TEST.md** and **docs/ROUTER_CURL_TESTS.md**.

---

## Non-Functional Goals

* async-first architecture
* strongly typed schemas
* modular design
* provider-agnostic integrations
* scalable
* Docker-ready
* auto-generated API docs (OpenAPI)

---

## Summary

This service functions as a **unified financial data gateway** that:

* aggregates multiple external providers
* supports REST and real-time streaming
* uses caching and background processing
* follows modern Python best practices

It is designed to resemble a **production-grade fintech backend**, not a simple demo application.
