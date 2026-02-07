# Polymarket Provider Architecture

## Overview

The Polymarket provider follows a clean DTO (Data Transfer Object) pattern that separates external API concerns from internal domain logic.

## Layer Structure

```
providers/events/polymarket/
├── dto.py                  # API DTOs + parsing + to_market_quote()
├── models.py                # PolymarketQuoteMetadata (for metadata dict shape)
├── resolver.py              # Symbol resolution with DTOs
└── polymarket_provider.py   # Orchestration (resolve → dto.to_market_quote())
```

## Data Flow

```
External API → DTO (validate + parse + derive) → dto.to_market_quote() → MarketQuote
```

### 1. DTO Layer (`dto.py`)

**Purpose**: Represent the external API and compile everything into parsed/derived fields. No separate mapper; the DTO produces `MarketQuote` via `to_market_quote()`.

**Classes**:
- `PolymarketMarketDTO`: Raw API fields + computed parsed fields (`outcomes_parsed`, `outcome_prices_parsed`, `clob_token_ids_parsed`) and derived fields (`value` = max probability, `symbol` = question, `volume_compiled`, `timestamp_compiled`, `top_outcome_index`, `top_outcome`). Methods: `to_market_quote()`, `to_metadata_dict()`.
- `PolymarketEventDTO`: `/events` response with nested markets.
- `PolymarketPriceUpdateDTO`: WebSocket price updates.

**MarketQuote contract for Polymarket**:
- `symbol` = market question (fallback: slug, condition_id)
- `value` = probability of the top outcome (max of outcome prices)
- `volume` = total USD volume
- `metadata` = full structure (outcomes, outcome_prices, slug, top_outcome, etc.)

**Benefits**:
- Single place for validation, parsing, and derivation
- No mapper module; DTO is the boundary and the compiler
- Type-safe and easy to test

### 2. Domain Models Layer (`models.py`)

**Purpose**: Shape of `MarketQuote.metadata` for Polymarket (used by DTO’s `to_metadata_dict()`).

**Classes**:
- `PolymarketQuoteMetadata`: question, outcomes, outcome_prices, condition_id, clob_token_ids, slug, top_outcome_index, top_outcome. Serialized to dict for `MarketQuote.metadata`.

### 3. Resolver Layer (`resolver.py`)

**Purpose**: Resolve symbol (slug or condition ID) to `PolymarketMarketDTO`.

**Methods**:
- `resolve(symbol)`: Returns `PolymarketMarketDTO` (from cache or API).
- `_fetch_by_slug()`, `_fetch_by_condition_id()`: Fetch and validate as DTO.

### 4. Provider Layer (`polymarket_provider.py`)

**Purpose**: Orchestrate resolution and produce `MarketQuote`s via DTO.

**Class**: `PolymarketProvider(EventsProviderABC)`

**Key Methods**:
```python
async def get_quote(self, symbol: str) -> MarketQuote:
    market_dto = await self._resolver.resolve(symbol)
    return market_dto.to_market_quote()

async def list_markets(...) -> list[MarketQuote]:
    events_data = response.json()
    for event_data in events_data:
        event_dto = PolymarketEventDTO.model_validate(event_data)
        for market_dto in event_dto.markets:
            quotes.append(market_dto.to_market_quote())
    return quotes
```

Streaming uses `market_dto.clob_token_ids_parsed` for token-to-slug mapping.

## Benefits of This Architecture

- **Single compilation point**: DTO validates, parses, and derives; no separate mapper.
- **Type safety**: Pydantic validates at the boundary; computed fields are typed.
- **Clear contract**: For Polymarket, symbol=question, value=max prob, volume=total USD.
- **Testability**: Mock DTOs or raw dicts → `PolymarketMarketDTO.model_validate()` → `to_market_quote()`.

## Example Usage

```python
provider = PolymarketProvider()

# resolve → DTO → to_market_quote()
quote = await provider.get_quote("will-bitcoin-reach-100k")
# quote.symbol = question, quote.value = max outcome probability, quote.volume = total USD

markets = await provider.list_markets(active=True, limit=10)
```

## Notes

- **No mapper**: All parsing and derivation live in the DTO; `to_market_quote()` and `to_metadata_dict()` produce the application output.
- **Cache**: Resolver uses `dict[str, PolymarketMarketDTO]`; cache stores validated DTOs.
- **Raw dicts**: To get a quote from a raw API dict, use `PolymarketMarketDTO.model_validate(market_dict).to_market_quote()`.
