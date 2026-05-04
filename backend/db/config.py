"""Database configuration helpers."""

from __future__ import annotations

import os


def get_database_url() -> str:
    """Return DATABASE_URL or raise a clear error if missing."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return database_url

