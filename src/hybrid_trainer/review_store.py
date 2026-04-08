from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Protocol

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


def build_review_store(
    *,
    session_path: str = "",
    audit_log_path: str = "",
    sqlite_db_path: str = "",
    session_id: str = "",
    bootstrap_session_path: str = "",
) -> ReviewStore:
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
