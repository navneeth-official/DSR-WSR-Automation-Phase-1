"""Read-only database access for the monthly report."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from monthly_report.config import database_url


@lru_cache
def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)
