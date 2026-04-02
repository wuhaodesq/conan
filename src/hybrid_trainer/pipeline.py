from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .reward_policy import RewardPolicy


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
    reward_policy: RewardPolicy = field(default_factory=RewardPolicy)


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

    def run_iteration(
        self,
        iteration: int,
        auto_score: float,
        node: DecisionNode,
        candidate_answer: str = "",
    ) -> IterationReport:
        decision, reason = self._decide(auto_score, candidate_answer)
        report = IterationReport(
            iteration=iteration,
            auto_score=auto_score,
            node=node,
            decision=decision,
            reason=reason,
        )
        self.history.append(report)
        return report

    def update_reward_policy(self, new_policy: RewardPolicy) -> None:
        self.config.reward_policy = new_policy

    def _decide(self, auto_score: float, candidate_answer: str) -> tuple[Decision, str]:
        policy = self.config.reward_policy
        threshold = policy.approve_threshold
        band = policy.review_band

        if policy.should_block_answer(candidate_answer):
            return Decision.BLOCK, f"命中策略黑名单词，按 {policy.version} 阻断"

        if auto_score >= threshold:
            return Decision.APPROVE, f"自动评估通过（{policy.version}），进入策略更新"

        if auto_score >= threshold - band:
            return Decision.REVIEW, f"处于灰区（{policy.version}），触发人工节点复核"

        return Decision.BLOCK, f"自动评估未达标（{policy.version}），回流样本池"
