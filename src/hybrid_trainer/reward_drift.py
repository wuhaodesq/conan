from __future__ import annotations

from dataclasses import dataclass

from .pipeline import Decision, IterationReport


@dataclass(slots=True)
class RewardDriftReport:
    total: int
    review_or_block: int
    approve: int
    drift_index: float


def compute_reward_drift(history: list[IterationReport]) -> RewardDriftReport:
    total = len(history)
    if total == 0:
        return RewardDriftReport(total=0, review_or_block=0, approve=0, drift_index=0.0)

    approve = sum(1 for item in history if item.decision == Decision.APPROVE)
    review_or_block = total - approve
    drift_index = review_or_block / total
    return RewardDriftReport(
        total=total,
        review_or_block=review_or_block,
        approve=approve,
        drift_index=drift_index,
    )
