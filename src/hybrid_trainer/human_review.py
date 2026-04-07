from __future__ import annotations

from dataclasses import dataclass, field

from .pipeline import Decision, DecisionNode


@dataclass(slots=True)
class HumanReviewItem:
    iteration: int
    node: DecisionNode
    auto_score: float
    auto_decision: Decision


@dataclass(slots=True)
class HumanReviewDecision:
    iteration: int
    final_decision: Decision
    reviewer: str
    note: str = ""


@dataclass
class HumanReviewQueue:
    pending: list[HumanReviewItem] = field(default_factory=list)
    resolved: list[HumanReviewDecision] = field(default_factory=list)

    def enqueue(self, item: HumanReviewItem) -> None:
        self.pending.append(item)

    def resolve(self, iteration: int, final_decision: Decision, reviewer: str, note: str = "") -> HumanReviewDecision:
        self.pending = [item for item in self.pending if item.iteration != iteration]
        decision = HumanReviewDecision(
            iteration=iteration,
            final_decision=final_decision,
            reviewer=reviewer,
            note=note,
        )
        self.resolved.append(decision)
        return decision
