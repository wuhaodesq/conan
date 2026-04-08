from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .pipeline import Decision, DecisionNode


@dataclass(slots=True)
class HumanReviewItem:
    iteration: int
    node: DecisionNode
    auto_score: float
    auto_decision: Decision

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "node": self.node.value,
            "auto_score": self.auto_score,
            "auto_decision": self.auto_decision.value,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "HumanReviewItem":
        return cls(
            iteration=int(payload["iteration"]),
            node=DecisionNode(payload["node"]),
            auto_score=float(payload["auto_score"]),
            auto_decision=Decision(payload["auto_decision"]),
        )


@dataclass(slots=True)
class HumanReviewDecision:
    iteration: int
    final_decision: Decision
    reviewer: str
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "final_decision": self.final_decision.value,
            "reviewer": self.reviewer,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "HumanReviewDecision":
        return cls(
            iteration=int(payload["iteration"]),
            final_decision=Decision(payload["final_decision"]),
            reviewer=str(payload["reviewer"]),
            note=str(payload.get("note", "")),
        )


@dataclass
class HumanReviewQueue:
    pending: list[HumanReviewItem] = field(default_factory=list)
    resolved: list[HumanReviewDecision] = field(default_factory=list)

    def enqueue(self, item: HumanReviewItem) -> None:
        self.pending.append(item)

    def get_pending(self, iteration: int) -> HumanReviewItem | None:
        for item in self.pending:
            if item.iteration == iteration:
                return item
        return None

    def resolve(self, iteration: int, final_decision: Decision, reviewer: str, note: str = "") -> HumanReviewDecision:
        if self.get_pending(iteration) is None:
            raise KeyError(f"Iteration {iteration} is not pending review")
        self.pending = [item for item in self.pending if item.iteration != iteration]
        decision = HumanReviewDecision(
            iteration=iteration,
            final_decision=final_decision,
            reviewer=reviewer,
            note=note,
        )
        self.resolved.append(decision)
        return decision


def save_review_batch(items: list[HumanReviewItem], path: str, budget: int) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "budget": budget,
        "items": [item.to_dict() for item in items],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_review_decisions(path: str) -> list[HumanReviewDecision]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("decisions", payload)
    return [HumanReviewDecision.from_dict(item) for item in items]
