"""Database engine and session management."""
import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlmodel import Session, create_engine

from market_data_agg.db.models import (  # noqa: F401  # pylint: disable=unused-import
    Alert, SQLModel, User, Watchlist)

_DEFAULT_URL = "postgresql://marketdata:marketdata@localhost:5432/marketdata"
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_URL)

# Synchronous engine for SQLModel (sync sessions)
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "0") == "1",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session; closes and rolls back on error."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Safe to call on startup (idempotent for existing tables)."""
    SQLModel.metadata.create_all(engine)
