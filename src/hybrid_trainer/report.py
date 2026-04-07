from __future__ import annotations

from dataclasses import dataclass

from .failure_analysis import FailureTaxonomy
from .metrics import DecisionMetrics
from .triggers import NodeTriggerRecommendation


@dataclass(slots=True)
class DecisionDashboard:
    metrics: DecisionMetrics
    failures: FailureTaxonomy
    recommended_nodes: list[str]

    def to_dict(self) -> dict:
        return {
            "metrics": {
                "total": self.metrics.total,
                "approve": self.metrics.approve,
                "review": self.metrics.review,
                "block": self.metrics.block,
            },
            "failures": {
                "low_score_block": self.failures.low_score_block,
                "policy_block": self.failures.policy_block,
                "verifier_override_review": self.failures.verifier_override_review,
                "generic_review": self.failures.generic_review,
                "total": self.failures.total_failures,
            },
            "recommended_nodes": self.recommended_nodes,
        }


def build_dashboard(
    metrics: DecisionMetrics,
    failures: FailureTaxonomy,
    recommendations: list[NodeTriggerRecommendation],
) -> DecisionDashboard:
    return DecisionDashboard(
        metrics=metrics,
        failures=failures,
        recommended_nodes=[item.node.value for item in recommendations],
    )
