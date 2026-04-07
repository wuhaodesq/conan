from __future__ import annotations

from dataclasses import dataclass

from .metrics import DecisionMetrics


@dataclass(slots=True)
class CostReport:
    total_iterations: int
    auto_evaluation_cost: float
    human_review_cost: float
    total_cost: float


def estimate_cost(
    metrics: DecisionMetrics,
    auto_cost_per_sample: float = 0.001,
    human_review_cost_per_sample: float = 0.05,
) -> CostReport:
    auto_cost = metrics.total * auto_cost_per_sample
    human_cost = (metrics.review + metrics.block) * human_review_cost_per_sample
    return CostReport(
        total_iterations=metrics.total,
        auto_evaluation_cost=auto_cost,
        human_review_cost=human_cost,
        total_cost=auto_cost + human_cost,
    )
