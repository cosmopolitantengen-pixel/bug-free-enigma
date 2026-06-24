from __future__ import annotations

import os

from app.persistence.postgres_store import PostgresStateStore
from app.persistence.sqlite_store import SQLiteStateStore
from app.persistence.store import StateStore
from app.secrets import read_secret


def create_state_store(
    *,
    sqlite_path: str | None = None,
    database_url: str | None = None,
) -> StateStore | None:
    """Build the configured persistence backend without making tests environment-dependent."""
    if sqlite_path is not None or database_url is not None:
        selected_sqlite_path = sqlite_path
        selected_database_url = database_url
    else:
        selected_sqlite_path = os.getenv("AI_COMPANY_OS_SQLITE_PATH")
        selected_database_url = read_secret("AI_COMPANY_OS_DATABASE_URL") or read_secret("DATABASE_URL")

    if selected_sqlite_path and selected_database_url:
        raise ValueError(
            "configure only one persistence backend: AI_COMPANY_OS_SQLITE_PATH or AI_COMPANY_OS_DATABASE_URL"
        )
    if selected_database_url:
        normalized_url = _normalize_postgres_url(selected_database_url)
        return PostgresStateStore(normalized_url)
    if selected_sqlite_path:
        return SQLiteStateStore(selected_sqlite_path)
    return None


def _normalize_postgres_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return "postgresql://" + database_url.removeprefix("postgresql+psycopg://")
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        return database_url
    raise ValueError("AI_COMPANY_OS_DATABASE_URL must use a PostgreSQL URL")
