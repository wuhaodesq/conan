from __future__ import annotations

from dataclasses import dataclass

from .metrics import DecisionMetrics
from .pipeline import DecisionNode


@dataclass(slots=True)
class NodeTriggerRecommendation:
    node: DecisionNode
    reason: str


def recommend_major_nodes(metrics: DecisionMetrics) -> list[NodeTriggerRecommendation]:
    if metrics.total == 0:
        return []

    recommendations: list[NodeTriggerRecommendation] = []
    review_ratio = metrics.review / metrics.total
    block_ratio = metrics.block / metrics.total

    if block_ratio >= 0.4:
        recommendations.append(
            NodeTriggerRecommendation(
                node=DecisionNode.FAILURE_REVIEW,
                reason="Block 比例过高，建议优先做失败模式诊断与定向修复。",
            )
        )

    if review_ratio >= 0.3:
        recommendations.append(
            NodeTriggerRecommendation(
                node=DecisionNode.REWARD_CALIBRATION,
                reason="Review 比例偏高，建议校准 reward 与自动评估边界。",
            )
        )

    if metrics.approve / metrics.total >= 0.85:
        recommendations.append(
            NodeTriggerRecommendation(
                node=DecisionNode.CURRICULUM_SHIFT,
                reason="Approve 比例高且稳定，建议进入下一阶段课程难度。",
            )
        )

    return recommendations
