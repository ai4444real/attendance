from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._lock, self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    request TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'codex',
                    status TEXT NOT NULL CHECK (
                        status IN ('queued','running','completed','failed','cancelled')
                    ),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    response TEXT,
                    error TEXT,
                    pid INTEGER,
                    session_id TEXT,
                    output TEXT NOT NULL DEFAULT '',
                    exit_code INTEGER
                );
                CREATE INDEX IF NOT EXISTS jobs_created_at
                    ON jobs(created_at DESC);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict | None:
        with self._lock, self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict]:
        with self._lock, self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._lock, self.connect() as conn:
            conn.execute(sql, params)

    def create_job(self, job: dict) -> None:
        with self._lock, self.connect() as conn:
            active = conn.execute(
                "SELECT id FROM jobs WHERE status IN ('queued','running') LIMIT 1"
            ).fetchone()
            if active:
                raise ActiveJobError(active["id"])
            conn.execute(
                """
                INSERT INTO jobs
                    (id, request, kind, status, created_at, session_id)
                VALUES (?, ?, ?, 'queued', ?, ?)
                """,
                (
                    job["id"],
                    job["request"],
                    job["kind"],
                    job["created_at"],
                    job.get("session_id"),
                ),
            )

    def setting(self, key: str) -> str | None:
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_setting(self, key: str, value: str | None) -> None:
        self.execute(
            """
            INSERT INTO settings(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


class ActiveJobError(Exception):
    def __init__(self, job_id: str):
        self.job_id = job_id
        super().__init__(job_id)

