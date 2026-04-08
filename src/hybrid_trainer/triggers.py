from __future__ import annotations

from dataclasses import dataclass

from .metrics import DecisionMetrics
from .pipeline import DecisionNode


@dataclass(slots=True)
class TriggerRuleConfig:
    min_samples: int = 1
    failure_review_block_ratio: float = 0.4
    reward_calibration_review_ratio: float = 0.3
    curriculum_shift_approve_ratio: float = 0.85

    def to_dict(self) -> dict:
        return {
            "min_samples": self.min_samples,
            "failure_review_block_ratio": self.failure_review_block_ratio,
            "reward_calibration_review_ratio": self.reward_calibration_review_ratio,
            "curriculum_shift_approve_ratio": self.curriculum_shift_approve_ratio,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TriggerRuleConfig":
        return cls(
            min_samples=int(payload.get("min_samples", 1)),
            failure_review_block_ratio=float(payload.get("failure_review_block_ratio", 0.4)),
            reward_calibration_review_ratio=float(payload.get("reward_calibration_review_ratio", 0.3)),
            curriculum_shift_approve_ratio=float(payload.get("curriculum_shift_approve_ratio", 0.85)),
        )


@dataclass(slots=True)
class NodeTriggerRecommendation:
    node: DecisionNode
    reason: str


def recommend_major_nodes(
    metrics: DecisionMetrics,
    config: TriggerRuleConfig | None = None,
) -> list[NodeTriggerRecommendation]:
    rules = config or TriggerRuleConfig()
    if metrics.total == 0 or metrics.total < rules.min_samples:
        return []

    recommendations: list[NodeTriggerRecommendation] = []
    review_ratio = metrics.review / metrics.total
    block_ratio = metrics.block / metrics.total

    if block_ratio >= rules.failure_review_block_ratio:
        recommendations.append(
            NodeTriggerRecommendation(
                node=DecisionNode.FAILURE_REVIEW,
                reason="Block 比例过高，建议优先做失败模式诊断与定向修复。",
            )
        )

    if review_ratio >= rules.reward_calibration_review_ratio:
        recommendations.append(
            NodeTriggerRecommendation(
                node=DecisionNode.REWARD_CALIBRATION,
                reason="Review 比例偏高，建议校准 reward 与自动评估边界。",
            )
        )

    if metrics.approve / metrics.total >= rules.curriculum_shift_approve_ratio:
        recommendations.append(
            NodeTriggerRecommendation(
                node=DecisionNode.CURRICULUM_SHIFT,
                reason="Approve 比例高且稳定，建议进入下一阶段课程难度。",
            )
        )

    return recommendations
