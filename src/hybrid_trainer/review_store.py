from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
from typing import Any, Protocol

try:  # pragma: no cover - dependency availability is environment specific
    import asyncpg
except ImportError:  # pragma: no cover - exercised when the optional dependency is absent
    asyncpg = None  # type: ignore[assignment]

try:  # pragma: no cover - dependency availability is environment specific
    import boto3
except ImportError:  # pragma: no cover - exercised when the optional dependency is absent
    boto3 = None  # type: ignore[assignment]

try:  # pragma: no cover - dependency availability is environment specific
    from botocore.config import Config
except ImportError:  # pragma: no cover - exercised when the optional dependency is absent
    Config = None  # type: ignore[assignment]

from .review_audit import (
    ReviewAuditEvent,
    append_review_audit_event,
    load_review_audit_events,
)
from .review_session import ReviewSession, load_review_session, save_review_session


def _object_key(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part.strip("/"))


def _is_missing_object_error(exc: Exception) -> bool:
    if isinstance(exc, (FileNotFoundError, KeyError)):
        return True
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error", {})
        if isinstance(error, dict):
            code = str(error.get("Code", ""))
            if code in {"404", "NoSuchBucket", "NoSuchKey", "NotFound"}:
                return True
    message = str(exc).lower()
    return any(token in message for token in ("no such key", "not found", "404"))


class ReviewStore(Protocol):
    def load_session(self) -> ReviewSession:
        ...

    def save_session(self, session: ReviewSession) -> None:
        ...

    def load_audit_events(self) -> list[ReviewAuditEvent]:
        ...

    def append_audit_event(self, event: ReviewAuditEvent) -> None:
        ...


@dataclass(slots=True)
class FileReviewStore:
    session_path: str
    audit_log_path: str

    def load_session(self) -> ReviewSession:
        return load_review_session(self.session_path)

    def save_session(self, session: ReviewSession) -> None:
        save_review_session(session, self.session_path)

    def load_audit_events(self) -> list[ReviewAuditEvent]:
        return load_review_audit_events(self.audit_log_path)

    def append_audit_event(self, event: ReviewAuditEvent) -> None:
        append_review_audit_event(self.audit_log_path, event)


@dataclass(slots=True)
class SqliteReviewStore:
    database_path: str
    session_id: str = ""
    bootstrap_session_path: str = ""

    def __post_init__(self) -> None:
        if not self.session_id and not self.bootstrap_session_path:
            raise ValueError("sqlite review store requires session_id or bootstrap_session_path")
        self._initialize()
        if self.bootstrap_session_path:
            bootstrap_session = load_review_session(self.bootstrap_session_path)
            if not self.session_id:
                self.session_id = bootstrap_session.session_id
            self._bootstrap_if_missing(bootstrap_session)

    def load_session(self) -> ReviewSession:
        row = self._fetch_session_row()
        if row is None:
            raise FileNotFoundError(f"review session {self.session_id!r} was not found in {self.database_path}")
        return ReviewSession.from_dict(json.loads(row[0]))

    def save_session(self, session: ReviewSession) -> None:
        self._validate_session_id(session.session_id)
        payload = json.dumps(session.to_dict(), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO review_sessions (session_id, payload, updated_at)
                VALUES (?, ?, ?)
                """,
                (session.session_id, payload, session.updated_at),
            )

    def load_audit_events(self) -> list[ReviewAuditEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT action, actor, role, session_id, payload, timestamp
                FROM review_audit_events
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (self.session_id,),
            ).fetchall()
        return [
            ReviewAuditEvent(
                action=str(action),
                actor=str(actor),
                role=str(role),
                session_id=str(session_id),
                payload=json.loads(payload),
                timestamp=str(timestamp),
            )
            for action, actor, role, session_id, payload, timestamp in rows
        ]

    def append_audit_event(self, event: ReviewAuditEvent) -> None:
        self._validate_session_id(event.session_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO review_audit_events (session_id, timestamp, action, actor, role, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.session_id,
                    event.timestamp,
                    event.action,
                    event.actor,
                    event.role,
                    json.dumps(event.payload, ensure_ascii=False),
                ),
            )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_sessions (
                    session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_review_audit_session_id
                ON review_audit_events (session_id, id)
                """
            )

    def _bootstrap_if_missing(self, session: ReviewSession) -> None:
        self._validate_session_id(session.session_id)
        if self._fetch_session_row() is None:
            self.save_session(session)

    def _fetch_session_row(self) -> tuple[str] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM review_sessions WHERE session_id = ?",
                (self.session_id,),
            ).fetchone()
        return tuple(row) if row is not None else None

    def _connect(self) -> sqlite3.Connection:
        database = Path(self.database_path)
        database.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(database)

    def _validate_session_id(self, session_id: str) -> None:
        if not self.session_id:
            self.session_id = session_id
        if session_id != self.session_id:
            raise ValueError(
                f"sqlite review store is scoped to session {self.session_id!r}, got {session_id!r}"
            )


@dataclass(slots=True)
class PostgresReviewStore:
    database_url: str
    session_id: str = ""
    bootstrap_session_path: str = ""
    timeout_seconds: int = 5

    def __post_init__(self) -> None:
        if asyncpg is None:  # pragma: no cover - dependency availability is environment specific
            raise RuntimeError("postgres review store requires asyncpg to be installed")
        if not self.session_id and not self.bootstrap_session_path:
            raise ValueError("postgres review store requires session_id or bootstrap_session_path")
        bootstrap_session = None
        if self.bootstrap_session_path:
            bootstrap_session = load_review_session(self.bootstrap_session_path)
            if not self.session_id:
                self.session_id = bootstrap_session.session_id
        self._run(self._initialize())
        if bootstrap_session is not None:
            self._run(self._bootstrap_if_missing(bootstrap_session))

    def load_session(self) -> ReviewSession:
        row = self._run(self._fetch_session_row())
        if row is None:
            raise FileNotFoundError(f"review session {self.session_id!r} was not found in {self.database_url}")
        return ReviewSession.from_dict(json.loads(row[0]))

    def save_session(self, session: ReviewSession) -> None:
        self._validate_session_id(session.session_id)
        payload = json.dumps(session.to_dict(), ensure_ascii=False)
        self._run(
            self._execute(
                """
                INSERT INTO review_sessions (session_id, payload, updated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id)
                DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
                """,
                session.session_id,
                payload,
                session.updated_at,
            )
        )

    def load_audit_events(self) -> list[ReviewAuditEvent]:
        rows = self._run(self._fetch_audit_rows())
        return [
            ReviewAuditEvent(
                action=str(action),
                actor=str(actor),
                role=str(role),
                session_id=str(session_id),
                payload=json.loads(payload),
                timestamp=str(timestamp),
            )
            for action, actor, role, session_id, payload, timestamp in rows
        ]

    def append_audit_event(self, event: ReviewAuditEvent) -> None:
        self._validate_session_id(event.session_id)
        self._run(
            self._execute(
                """
                INSERT INTO review_audit_events (session_id, timestamp, action, actor, role, payload)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                event.session_id,
                event.timestamp,
                event.action,
                event.actor,
                event.role,
                json.dumps(event.payload, ensure_ascii=False),
            )
        )

    def _validate_session_id(self, session_id: str) -> None:
        if not self.session_id:
            self.session_id = session_id
        if session_id != self.session_id:
            raise ValueError(
                f"postgres review store is scoped to session {self.session_id!r}, got {session_id!r}"
            )

    def _run(self, awaitable):
        return asyncio.run(awaitable)

    async def _connect(self):
        assert asyncpg is not None
        return await asyncpg.connect(dsn=self.database_url, timeout=self.timeout_seconds)

    async def _initialize(self) -> None:
        connection = await self._connect()
        try:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_sessions (
                    session_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_audit_events (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            await connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_review_audit_session_id
                ON review_audit_events (session_id, id)
                """
            )
        finally:
            await connection.close()

    async def _bootstrap_if_missing(self, session: ReviewSession) -> None:
        if await self._fetch_session_row() is None:
            await self._save_session(session)

    async def _fetch_session_row(self) -> tuple[str] | None:
        connection = await self._connect()
        try:
            row = await connection.fetchrow(
                "SELECT payload FROM review_sessions WHERE session_id = $1",
                self.session_id,
            )
        finally:
            await connection.close()
        return tuple(row) if row is not None else None

    async def _fetch_audit_rows(self) -> list[tuple]:
        connection = await self._connect()
        try:
            rows = await connection.fetch(
                """
                SELECT action, actor, role, session_id, payload, timestamp
                FROM review_audit_events
                WHERE session_id = $1
                ORDER BY id ASC
                """,
                self.session_id,
            )
        finally:
            await connection.close()
        return [tuple(row) for row in rows]

    async def _save_session(self, session: ReviewSession) -> None:
        payload = json.dumps(session.to_dict(), ensure_ascii=False)
        await self._execute(
            """
            INSERT INTO review_sessions (session_id, payload, updated_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (session_id)
            DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
            """,
            session.session_id,
            payload,
            session.updated_at,
        )

    async def _execute(self, statement: str, *args) -> None:
        connection = await self._connect()
        try:
            await connection.execute(statement, *args)
        finally:
            await connection.close()


@dataclass(slots=True)
class ObjectStorageReviewStore:
    bucket_name: str
    session_id: str = ""
    bootstrap_session_path: str = ""
    object_prefix: str = "review"
    endpoint_url: str = ""
    region_name: str = ""
    use_ssl: bool = True
    force_path_style: bool = False
    timeout_seconds: int = 5
    client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if boto3 is None:  # pragma: no cover - dependency availability is environment specific
            raise RuntimeError("object storage review store requires boto3 to be installed")
        if not self.bucket_name:
            raise ValueError("object storage review store requires bucket_name")
        if not self.session_id and not self.bootstrap_session_path:
            raise ValueError("object storage review store requires session_id or bootstrap_session_path")
        client_kwargs: dict[str, Any] = {"use_ssl": self.use_ssl}
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.region_name:
            client_kwargs["region_name"] = self.region_name
        if Config is not None and (self.force_path_style or self.timeout_seconds > 0):
            config_kwargs: dict[str, Any] = {}
            if self.force_path_style:
                config_kwargs["s3"] = {"addressing_style": "path"}
            if self.timeout_seconds > 0:
                config_kwargs["connect_timeout"] = self.timeout_seconds
                config_kwargs["read_timeout"] = self.timeout_seconds
            if config_kwargs:
                client_kwargs["config"] = Config(**config_kwargs)
        self.client = boto3.client("s3", **client_kwargs)

        bootstrap_session = None
        if self.bootstrap_session_path:
            bootstrap_session = load_review_session(self.bootstrap_session_path)
            self._validate_session_id(bootstrap_session.session_id)
        if bootstrap_session is not None:
            self._bootstrap_if_missing(bootstrap_session)

    def load_session(self) -> ReviewSession:
        payload = self._read_object_text(self._session_key())
        if payload is None:
            raise FileNotFoundError(f"review session {self.session_id!r} was not found in bucket {self.bucket_name}")
        return ReviewSession.from_dict(json.loads(payload))

    def save_session(self, session: ReviewSession) -> None:
        self._validate_session_id(session.session_id)
        self._write_object_text(
            self._session_key(),
            json.dumps(session.to_dict(), ensure_ascii=False),
            content_type="application/json",
        )

    def load_audit_events(self) -> list[ReviewAuditEvent]:
        payload = self._read_object_text(self._audit_key())
        if not payload:
            return []
        lines = [line for line in payload.splitlines() if line.strip()]
        return [ReviewAuditEvent(**json.loads(line)) for line in lines]

    def append_audit_event(self, event: ReviewAuditEvent) -> None:
        self._validate_session_id(event.session_id)
        existing = self._read_object_text(self._audit_key()) or ""
        lines = [line for line in existing.splitlines() if line.strip()]
        lines.append(json.dumps(event.to_dict(), ensure_ascii=False))
        self._write_object_text(
            self._audit_key(),
            "\n".join(lines) + "\n",
            content_type="application/x-ndjson",
        )

    def _session_key(self) -> str:
        return _object_key(self.object_prefix, self.session_id, "session.json")

    def _audit_key(self) -> str:
        return _object_key(self.object_prefix, self.session_id, "audit.jsonl")

    def _bootstrap_if_missing(self, session: ReviewSession) -> None:
        if self._read_object_text(self._session_key()) is None:
            self.save_session(session)

    def _validate_session_id(self, session_id: str) -> None:
        if not self.session_id:
            self.session_id = session_id
        if session_id != self.session_id:
            raise ValueError(
                f"object storage review store is scoped to session {self.session_id!r}, got {session_id!r}"
            )

    def _read_object_text(self, key: str) -> str | None:
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        except Exception as exc:  # pragma: no cover - exercised in integration tests
            if _is_missing_object_error(exc):
                return None
            raise
        body = response.get("Body")
        if body is None:
            return ""
        if hasattr(body, "read"):
            raw = body.read()
            if hasattr(body, "close"):
                body.close()
        else:
            raw = body
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)

    def _write_object_text(self, key: str, text: str, *, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=text.encode("utf-8"),
            ContentType=content_type,
        )


def build_review_store(
    *,
    session_path: str = "",
    audit_log_path: str = "",
    sqlite_db_path: str = "",
    postgres_dsn: str = "",
    object_store_bucket: str = "",
    object_store_prefix: str = "review",
    object_store_endpoint_url: str = "",
    object_store_region_name: str = "",
    object_store_use_ssl: bool = True,
    object_store_force_path_style: bool = False,
    object_store_timeout_seconds: int = 5,
    session_id: str = "",
    bootstrap_session_path: str = "",
) -> ReviewStore:
    backend_count = sum(
        bool(item)
        for item in (
            sqlite_db_path,
            postgres_dsn,
            object_store_bucket,
        )
    )
    if backend_count > 1:
        raise ValueError("configure only one persistent review store backend")
    if postgres_dsn:
        return PostgresReviewStore(
            database_url=postgres_dsn,
            session_id=session_id,
            bootstrap_session_path=bootstrap_session_path or session_path,
        )
    if sqlite_db_path:
        return SqliteReviewStore(
            database_path=sqlite_db_path,
            session_id=session_id,
            bootstrap_session_path=bootstrap_session_path or session_path,
        )
    if object_store_bucket:
        return ObjectStorageReviewStore(
            bucket_name=object_store_bucket,
            session_id=session_id,
            bootstrap_session_path=bootstrap_session_path or session_path,
            object_prefix=object_store_prefix,
            endpoint_url=object_store_endpoint_url,
            region_name=object_store_region_name,
            use_ssl=object_store_use_ssl,
            force_path_style=object_store_force_path_style,
            timeout_seconds=object_store_timeout_seconds,
        )
    if not session_path:
        raise ValueError("file review store requires session_path")
    if not audit_log_path:
        raise ValueError("file review store requires audit_log_path")
    return FileReviewStore(session_path=session_path, audit_log_path=audit_log_path)
