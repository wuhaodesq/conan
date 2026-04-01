from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    APPROVE = "approve"
    REVIEW = "review"
    BLOCK = "block"


class DecisionNode(str, Enum):
    REWARD_CALIBRATION = "reward_calibration"
    FAILURE_REVIEW = "failure_review"
    CURRICULUM_SHIFT = "curriculum_shift"


@dataclass(slots=True)
class PipelineConfig:
    auto_pass_threshold: float = 0.8
    review_band: float = 0.15


@dataclass(slots=True)
class IterationReport:
    iteration: int
    auto_score: float
    node: DecisionNode
    decision: Decision
    reason: str


@dataclass
class TrainingPipeline:
    config: PipelineConfig = field(default_factory=PipelineConfig)
    history: list[IterationReport] = field(default_factory=list)

    def run_iteration(self, iteration: int, auto_score: float, node: DecisionNode) -> IterationReport:
        decision, reason = self._decide(auto_score)
        report = IterationReport(
            iteration=iteration,
            auto_score=auto_score,
            node=node,
            decision=decision,
            reason=reason,
        )
        self.history.append(report)
        return report

    def _decide(self, auto_score: float) -> tuple[Decision, str]:
        threshold = self.config.auto_pass_threshold
        band = self.config.review_band

        if auto_score >= threshold:
            return Decision.APPROVE, "自动评估通过，进入策略更新"

        if auto_score >= threshold - band:
            return Decision.REVIEW, "处于灰区，触发人工节点复核"

        return Decision.BLOCK, "自动评估未达标，回流样本池"
