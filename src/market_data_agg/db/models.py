"""Database models for the market data aggregation service.

Only user/application state is persisted. Market quotes are fetched on demand
and cached in Redis; they are not stored in PostgreSQL.
"""
from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """User account for authentication and personalization."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: str = Field(default="user")  # user | admin
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Watchlist(SQLModel, table=True):
    """Stores references to assets/events the user follows."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    source: str  # stock | crypto | polymarket
    symbol: str  # AAPL | BTC | event/market id
    external_id: str | None = None  # provider-specific id (e.g. token_id)


class Alert(SQLModel, table=True):
    """Price or probability alerts for a user."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    source: str
    symbol: str
    price_above: float | None = None
    price_below: float | None = None
