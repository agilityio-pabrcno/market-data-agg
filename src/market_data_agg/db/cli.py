"""CLI entry points for database migrations (Alembic)."""
import subprocess
import sys
from pathlib import Path

# Project root: .../src/market_data_agg/db/cli.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run_alembic(*args: str) -> None:
    """Run alembic from the project root."""
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_PROJECT_ROOT,
        check=True,
    )


def generate() -> None:
    """Run alembic revision --autogenerate. Pass -m "message" for the revision message."""
    _run_alembic("revision", "--autogenerate", *sys.argv[1:])


def migrate() -> None:
    """Run alembic upgrade head. Pass a revision as first arg to upgrade to that instead."""
    revision = sys.argv[1] if len(sys.argv) > 1 else "head"
    _run_alembic("upgrade", revision, *sys.argv[2:])
