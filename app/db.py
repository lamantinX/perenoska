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

CREATE TABLE IF NOT EXISTS transfer_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    base_token TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    operation TEXT NOT NULL,
    request_url TEXT NOT NULL,
    request_headers TEXT NOT NULL,
    request_body TEXT NOT NULL,
    response_headers TEXT NOT NULL,
    response_body TEXT NOT NULL,
    source_marketplace TEXT,
    target_marketplace TEXT,
    job_id INTEGER,
    status_code INTEGER,
    duration_ms INTEGER,
    error_text TEXT
);

CREATE TABLE IF NOT EXISTS dictionary_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_connection_id INTEGER NOT NULL,
    target_connection_id INTEGER NOT NULL,
    mapping_type TEXT NOT NULL,
    source_value_raw TEXT NOT NULL,
    source_value_normalized TEXT NOT NULL,
    target_attribute_id INTEGER NOT NULL,
    target_dictionary_value_id INTEGER NOT NULL,
    target_dictionary_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_connection_id, target_connection_id, mapping_type, source_value_normalized),
    FOREIGN KEY(source_connection_id) REFERENCES marketplace_connections(id),
    FOREIGN KEY(target_connection_id) REFERENCES marketplace_connections(id)
);

CREATE TABLE IF NOT EXISTS mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_connection_id INTEGER NOT NULL,
    target_connection_id INTEGER NOT NULL,
    mapping_type TEXT NOT NULL,
    source_marketplace TEXT NOT NULL,
    target_marketplace TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_label TEXT NOT NULL,
    source_context_json TEXT NOT NULL,
    target_key TEXT NOT NULL,
    target_label TEXT NOT NULL,
    target_context_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_connection_id, target_connection_id, mapping_type, source_key),
    FOREIGN KEY(source_connection_id) REFERENCES marketplace_connections(id),
    FOREIGN KEY(target_connection_id) REFERENCES marketplace_connections(id)
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

    def create_transfer_log(
        self,
        *,
        created_at: str,
        base_token: str,
        sequence_no: int,
        token: str,
        event_type: str,
        operation: str,
        request_url: str,
        request_headers: dict[str, Any],
        request_body: dict[str, Any] | list[Any] | str | None,
        response_headers: dict[str, Any],
        response_body: dict[str, Any] | list[Any] | str | None,
        source_marketplace: str | None,
        target_marketplace: str | None,
        job_id: int | None,
        status_code: int | None,
        duration_ms: int | None,
        error_text: str | None,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO transfer_logs (
                    created_at, base_token, sequence_no, token, event_type, operation,
                    request_url, request_headers, request_body, response_headers, response_body,
                    source_marketplace, target_marketplace, job_id, status_code, duration_ms, error_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    base_token,
                    sequence_no,
                    token,
                    event_type,
                    operation,
                    request_url,
                    json.dumps(request_headers, ensure_ascii=True),
                    json.dumps(request_body, ensure_ascii=True),
                    json.dumps(response_headers, ensure_ascii=True),
                    json.dumps(response_body, ensure_ascii=True),
                    source_marketplace,
                    target_marketplace,
                    job_id,
                    status_code,
                    duration_ms,
                    error_text,
                ),
            )
            row = connection.execute("SELECT * FROM transfer_logs WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return self._deserialize_transfer_log(self._row_to_dict(row) or {})

    def list_transfer_logs(self, *, base_token: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM transfer_logs"
        params: list[Any] = []
        if base_token is not None:
            query += " WHERE base_token = ?"
            params.append(base_token)
        query += " ORDER BY sequence_no"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            return [self._deserialize_transfer_log(self._row_to_dict(row) or {}) for row in rows]

    def save_dictionary_mapping(
        self,
        *,
        source_connection_id: int,
        target_connection_id: int,
        mapping_type: str,
        source_value_raw: str,
        source_value_normalized: str,
        target_attribute_id: int,
        target_dictionary_value_id: int,
        target_dictionary_value: str,
        now: str,
    ) -> int:
        return self.save_mapping(
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            mapping_type=f"dictionary_{mapping_type}",
            source_marketplace="wb",
            target_marketplace="ozon",
            source_key=f"{mapping_type}:{source_value_normalized}",
            source_label=source_value_raw,
            source_context={},
            target_key=f"dict:{target_dictionary_value_id}",
            target_label=target_dictionary_value,
            target_context={
                "attribute_id": target_attribute_id,
                "target_dictionary_value_id": target_dictionary_value_id,
                "target_dictionary_value": target_dictionary_value,
            },
            now=now,
        )

    def save_mapping(
        self,
        *,
        source_connection_id: int,
        target_connection_id: int,
        mapping_type: str,
        source_marketplace: str,
        target_marketplace: str,
        source_key: str,
        source_label: str,
        source_context: dict[str, Any],
        target_key: str,
        target_label: str,
        target_context: dict[str, Any],
        now: str,
    ) -> int:
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT id FROM mappings
                WHERE source_connection_id = ?
                  AND target_connection_id = ?
                  AND mapping_type = ?
                  AND source_key = ?
                """,
                (source_connection_id, target_connection_id, mapping_type, source_key),
            ).fetchone()
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO mappings (
                        source_connection_id,
                        target_connection_id,
                        mapping_type,
                        source_marketplace,
                        target_marketplace,
                        source_key,
                        source_label,
                        source_context_json,
                        target_key,
                        target_label,
                        target_context_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_connection_id,
                        target_connection_id,
                        mapping_type,
                        source_marketplace,
                        target_marketplace,
                        source_key,
                        source_label,
                        json.dumps(source_context, ensure_ascii=True),
                        target_key,
                        target_label,
                        json.dumps(target_context, ensure_ascii=True),
                        now,
                        now,
                    ),
                )
                return int(cursor.lastrowid)

            connection.execute(
                """
                UPDATE mappings
                SET source_marketplace = ?,
                    target_marketplace = ?,
                    source_label = ?,
                    source_context_json = ?,
                    target_key = ?,
                    target_label = ?,
                    target_context_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    source_marketplace,
                    target_marketplace,
                    source_label,
                    json.dumps(source_context, ensure_ascii=True),
                    target_key,
                    target_label,
                    json.dumps(target_context, ensure_ascii=True),
                    now,
                    int(existing["id"]),
                ),
            )
            return int(existing["id"])

    def get_mapping(
        self,
        *,
        source_connection_id: int,
        target_connection_id: int,
        mapping_type: str,
        source_key: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM mappings
                WHERE source_connection_id = ?
                  AND target_connection_id = ?
                  AND mapping_type = ?
                  AND source_key = ?
                """,
                (source_connection_id, target_connection_id, mapping_type, source_key),
            ).fetchone()
            return self._row_to_dict(row)

    def list_mappings(
        self,
        *,
        source_connection_id: int,
        target_connection_id: int,
        mapping_type: str | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT * FROM mappings
            WHERE source_connection_id = ? AND target_connection_id = ?
        """
        params: list[Any] = [source_connection_id, target_connection_id]
        if mapping_type is not None:
            query += " AND mapping_type = ?"
            params.append(mapping_type)
        query += " ORDER BY source_key"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            return [self._row_to_dict(row) or {} for row in rows]

    def get_dictionary_mapping(
        self,
        *,
        source_connection_id: int,
        target_connection_id: int,
        mapping_type: str,
        source_value_normalized: str,
    ) -> dict[str, Any] | None:
        row = self.get_mapping(
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            mapping_type=f"dictionary_{mapping_type}",
            source_key=f"{mapping_type}:{source_value_normalized}",
        )
        if row is None:
            return None
        target_context = json.loads(row["target_context_json"])
        return {
            "id": row["id"],
            "source_connection_id": row["source_connection_id"],
            "target_connection_id": row["target_connection_id"],
            "mapping_type": mapping_type,
            "source_value_raw": row["source_label"],
            "source_value_normalized": source_value_normalized,
            "target_attribute_id": int(target_context.get("attribute_id") or 0),
            "target_dictionary_value_id": int(
                target_context.get("target_dictionary_value_id")
                or str(row.get("target_key") or "").removeprefix("dict:")
                or 0
            ),
            "target_dictionary_value": str(target_context.get("target_dictionary_value") or row["target_label"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_dictionary_mappings(
        self,
        *,
        source_connection_id: int,
        target_connection_id: int,
        mapping_type: str | None = None,
    ) -> list[dict[str, Any]]:
        generalized_type = f"dictionary_{mapping_type}" if mapping_type is not None else None
        rows = self.list_mappings(
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            mapping_type=generalized_type,
        )
        normalized: list[dict[str, Any]] = []
        for row in rows:
            target_context = json.loads(row["target_context_json"])
            source_key = str(row["source_key"])
            _, _, source_value_normalized = source_key.partition(":")
            normalized.append(
                {
                    "id": row["id"],
                    "source_connection_id": row["source_connection_id"],
                    "target_connection_id": row["target_connection_id"],
                    "mapping_type": mapping_type or str(row["mapping_type"]).removeprefix("dictionary_"),
                    "source_value_raw": row["source_label"],
                    "source_value_normalized": source_value_normalized,
                    "target_attribute_id": int(target_context.get("attribute_id") or 0),
                    "target_dictionary_value_id": int(
                        target_context.get("target_dictionary_value_id")
                        or str(row.get("target_key") or "").removeprefix("dict:")
                        or 0
                    ),
                    "target_dictionary_value": str(target_context.get("target_dictionary_value") or row["target_label"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return normalized

    @staticmethod
    def _deserialize_job(data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return data
        data["payload_json"] = json.loads(data["payload_json"])
        data["result_json"] = json.loads(data["result_json"])
        return data

    @staticmethod
    def _deserialize_transfer_log(data: dict[str, Any]) -> dict[str, Any]:
        if not data:
            return data
        data["request_headers"] = json.loads(data["request_headers"])
        data["request_body"] = json.loads(data["request_body"])
        data["response_headers"] = json.loads(data["response_headers"])
        data["response_body"] = json.loads(data["response_body"])
        return data
