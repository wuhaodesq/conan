from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .strategy import TrainingStrategy


@dataclass(slots=True)
class EngineStateSnapshot:
    strategy: TrainingStrategy
    curriculum_index: int
    history_count: int
    pending_reviews: int

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "curriculum_index": self.curriculum_index,
            "history_count": self.history_count,
            "pending_reviews": self.pending_reviews,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "EngineStateSnapshot":
        return cls(
            strategy=TrainingStrategy(payload["strategy"]),
            curriculum_index=int(payload["curriculum_index"]),
            history_count=int(payload["history_count"]),
            pending_reviews=int(payload["pending_reviews"]),
        )


def save_snapshot(snapshot: EngineStateSnapshot, path: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2) + "\n")
    return output


def load_snapshot(path: str) -> EngineStateSnapshot:
    payload = json.loads(Path(path).read_text())
    return EngineStateSnapshot.from_dict(payload)
