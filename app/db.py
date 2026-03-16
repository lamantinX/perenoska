from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS marketplace_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    marketplace TEXT NOT NULL,
    credentials_encrypted TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, marketplace),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS transfer_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source_marketplace TEXT NOT NULL,
    target_marketplace TEXT NOT NULL,
    status TEXT NOT NULL,
    external_task_id TEXT,
    error_message TEXT,
    payload_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

    def create_user(self, *, email: str, password_hash: str, created_at: str) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, password_hash, created_at),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return self._row_to_dict(row) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            return self._row_to_dict(row)

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_dict(row)

    def create_session(
        self,
        *,
        token: str,
        user_id: int,
        expires_at: str,
        created_at: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, user_id, expires_at, created_at),
            )

    def get_session(self, token: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
            return self._row_to_dict(row)

    def upsert_connection(
        self,
        *,
        user_id: int,
        marketplace: str,
        credentials_encrypted: str,
        now: str,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM marketplace_connections
                WHERE user_id = ? AND marketplace = ?
                """,
                (user_id, marketplace),
            ).fetchone()
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO marketplace_connections
                    (user_id, marketplace, credentials_encrypted, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, marketplace, credentials_encrypted, now, now),
                )
                row = connection.execute(
                    "SELECT * FROM marketplace_connections WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
            else:
                connection.execute(
                    """
                    UPDATE marketplace_connections
                    SET credentials_encrypted = ?, updated_at = ?
                    WHERE user_id = ? AND marketplace = ?
                    """,
                    (credentials_encrypted, now, user_id, marketplace),
                )
                row = connection.execute(
                    """
                    SELECT * FROM marketplace_connections
                    WHERE user_id = ? AND marketplace = ?
                    """,
                    (user_id, marketplace),
                ).fetchone()
            return self._row_to_dict(row) or {}

    def list_connections(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM marketplace_connections
                WHERE user_id = ?
                ORDER BY marketplace
                """,
                (user_id,),
            ).fetchall()
            return [self._row_to_dict(row) or {} for row in rows]

    def get_connection(self, user_id: int, marketplace: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM marketplace_connections
                WHERE user_id = ? AND marketplace = ?
                """,
                (user_id, marketplace),
            ).fetchone()
            return self._row_to_dict(row)

    def create_transfer_job(
        self,
        *,
        user_id: int,
        source_marketplace: str,
        target_marketplace: str,
        status: str,
        payload: dict[str, Any],
        result: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transfer_jobs
                (user_id, source_marketplace, target_marketplace, status, external_task_id,
                 error_message, payload_json, result_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    source_marketplace,
                    target_marketplace,
                    status,
                    json.dumps(payload, ensure_ascii=True),
                    json.dumps(result, ensure_ascii=True),
                    created_at,
                    created_at,
                ),
            )
            row = connection.execute("SELECT * FROM transfer_jobs WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return self._deserialize_job(self._row_to_dict(row) or {})

    def update_transfer_job(
        self,
        *,
        job_id: int,
        status: str,
        updated_at: str,
        external_task_id: str | None = None,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            current = connection.execute("SELECT * FROM transfer_jobs WHERE id = ?", (job_id,)).fetchone()
            current_row = self._row_to_dict(current) or {}
            payload_json = json.dumps(payload, ensure_ascii=True) if payload is not None else current_row["payload_json"]
            result_json = json.dumps(result, ensure_ascii=True) if result is not None else current_row["result_json"]
            connection.execute(
                """
                UPDATE transfer_jobs
                SET status = ?,
                    external_task_id = ?,
                    error_message = ?,
                    payload_json = ?,
                    result_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    external_task_id if external_task_id is not None else current_row.get("external_task_id"),
                    error_message if error_message is not None else current_row.get("error_message"),
                    payload_json,
                    result_json,
                    updated_at,
                    job_id,
                ),
            )
            row = connection.execute("SELECT * FROM transfer_jobs WHERE id = ?", (job_id,)).fetchone()
            return self._deserialize_job(self._row_to_dict(row) or {})

    def get_transfer_job(self, user_id: int, job_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM transfer_jobs WHERE id = ? AND user_id = ?",
                (job_id, user_id),
            ).fetchone()
            data = self._row_to_dict(row)
            if data is None:
                return None
            return self._deserialize_job(data)

    def list_transfer_jobs(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM transfer_jobs
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (user_id,),
            ).fetchall()
            return [self._deserialize_job(self._row_to_dict(row) or {}) for row in rows]

    @staticmethod
    def _deserialize_job(data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return data
        data["payload_json"] = json.loads(data["payload_json"])
        data["result_json"] = json.loads(data["result_json"])
        return data
