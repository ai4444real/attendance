"""PostgreSQL connection helpers."""

from __future__ import annotations

from contextlib import contextmanager

import psycopg

from .config import get_database_url


@contextmanager
def get_db_connection():
    """Yield a PostgreSQL connection using DATABASE_URL."""
    connection = psycopg.connect(get_database_url())
    try:
        yield connection
    finally:
        connection.close()

