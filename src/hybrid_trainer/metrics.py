from __future__ import annotations

from dataclasses import dataclass

from .pipeline import Decision, IterationReport


@dataclass(slots=True)
class DecisionMetrics:
    total: int
    approve: int
    review: int
    block: int


def summarize_decisions(history: list[IterationReport]) -> DecisionMetrics:
    approve = sum(1 for item in history if item.decision == Decision.APPROVE)
    review = sum(1 for item in history if item.decision == Decision.REVIEW)
    block = sum(1 for item in history if item.decision == Decision.BLOCK)
    return DecisionMetrics(total=len(history), approve=approve, review=review, block=block)
