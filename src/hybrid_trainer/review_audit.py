from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass(slots=True)
class ReviewAuditEvent:
    action: str
    actor: str
    role: str
    session_id: str
    payload: dict
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def create_review_audit_event(
    action: str,
    actor: str,
    role: str,
    session_id: str,
    payload: dict,
) -> ReviewAuditEvent:
    return ReviewAuditEvent(
        action=action,
        actor=actor,
        role=role,
        session_id=session_id,
        payload=payload,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def append_review_audit_event(path: str, event: ReviewAuditEvent) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
    return output


def load_review_audit_events(path: str) -> list[ReviewAuditEvent]:
    source = Path(path)
    if not source.exists():
        return []
    lines = [line for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [ReviewAuditEvent(**json.loads(line)) for line in lines]
