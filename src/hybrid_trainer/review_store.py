from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Protocol

try:  # pragma: no cover - dependency availability is environment specific
    import asyncpg
except ImportError:  # pragma: no cover - exercised when the optional dependency is absent
    asyncpg = None  # type: ignore[assignment]

from .review_audit import (
    ReviewAuditEvent,
    append_review_audit_event,
    load_review_audit_events,
)
from .review_session import ReviewSession, load_review_session, save_review_session


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


def build_review_store(
    *,
    session_path: str = "",
    audit_log_path: str = "",
    sqlite_db_path: str = "",
    postgres_dsn: str = "",
    session_id: str = "",
    bootstrap_session_path: str = "",
) -> ReviewStore:
    if sqlite_db_path and postgres_dsn:
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
    if not session_path:
        raise ValueError("file review store requires session_path")
    if not audit_log_path:
        raise ValueError("file review store requires audit_log_path")
    return FileReviewStore(session_path=session_path, audit_log_path=audit_log_path)
