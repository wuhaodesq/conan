from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass(slots=True)
class ExperimentEvent:
    event_type: str
    payload: dict
    timestamp: str


@dataclass
class ExperimentTracker:
    events: list[ExperimentEvent] = field(default_factory=list)

    def track(self, event_type: str, payload: dict) -> ExperimentEvent:
        event = ExperimentEvent(
            event_type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.events.append(event)
        return event

    def export_jsonl(self, path: str) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(asdict(event), ensure_ascii=False) for event in self.events]
        output.write_text("\n".join(lines) + ("\n" if lines else ""))
        return output
