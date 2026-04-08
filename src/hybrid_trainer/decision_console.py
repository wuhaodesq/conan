from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .active_learning import ActiveLearningCandidate
from .cost import CostReport
from .report import DecisionDashboard
from .reward_drift import RewardDriftReport
from .strategy import StrategySwitchRecord


@dataclass(slots=True)
class MajorNodeRecommendationView:
    node: str
    reason: str

    def to_dict(self) -> dict:
        return {"node": self.node, "reason": self.reason}


@dataclass(slots=True)
class ReviewQueueItemView:
    iteration: int
    node: str
    auto_score: float
    auto_decision: str
    risk_score: float

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "node": self.node,
            "auto_score": self.auto_score,
            "auto_decision": self.auto_decision,
            "risk_score": round(self.risk_score, 4),
        }


@dataclass(slots=True)
class ReviewQueueConsole:
    pending_count: int
    resolved_count: int
    budget: int
    prioritized_items: list[ReviewQueueItemView]
    recent_resolutions: list[dict]

    def to_dict(self) -> dict:
        return {
            "pending_count": self.pending_count,
            "resolved_count": self.resolved_count,
            "budget": self.budget,
            "prioritized_items": [item.to_dict() for item in self.prioritized_items],
            "recent_resolutions": list(self.recent_resolutions),
        }


@dataclass(slots=True)
class ActiveLearningConsole:
    threshold: float
    limit: int
    candidates: list[ActiveLearningCandidate]

    def to_dict(self) -> dict:
        return {
            "threshold": self.threshold,
            "limit": self.limit,
            "candidates": [
                {
                    "iteration": item.iteration,
                    "score": item.score,
                    "uncertainty": round(item.uncertainty, 4),
                }
                for item in self.candidates
            ],
        }


@dataclass(slots=True)
class PolicyVersionView:
    version: str
    note: str
    is_active: bool
    policy: dict

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "note": self.note,
            "is_active": self.is_active,
            "policy": self.policy,
        }


@dataclass(slots=True)
class PolicyConsoleView:
    active_version: str | None
    available_versions: list[PolicyVersionView]

    def to_dict(self) -> dict:
        return {
            "active_version": self.active_version,
            "available_versions": [item.to_dict() for item in self.available_versions],
        }


@dataclass(slots=True)
class StrategyConsoleView:
    current: str
    recommended: str
    reason: str
    history: list[StrategySwitchRecord]

    def to_dict(self) -> dict:
        return {
            "current": self.current,
            "recommended": self.recommended,
            "reason": self.reason,
            "history": [
                {
                    "from": item.from_strategy.value,
                    "to": item.to_strategy.value,
                    "reason": item.reason,
                }
                for item in self.history
            ],
        }


@dataclass(slots=True)
class CurriculumConsoleView:
    current_stage: str
    next_stage: str | None
    next_stage_min_approve_ratio: float | None
    history: list[dict]

    def to_dict(self) -> dict:
        return {
            "current_stage": self.current_stage,
            "next_stage": self.next_stage,
            "next_stage_min_approve_ratio": self.next_stage_min_approve_ratio,
            "history": list(self.history),
        }


@dataclass(slots=True)
class RecentEventView:
    event_type: str
    timestamp: str
    payload: dict

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


@dataclass(slots=True)
class DecisionConsole:
    dashboard: DecisionDashboard
    major_node_recommendations: list[MajorNodeRecommendationView]
    review_queue: ReviewQueueConsole
    review_consensus: dict
    active_learning: ActiveLearningConsole
    reward_drift: RewardDriftReport
    cost: CostReport
    policy: PolicyConsoleView
    strategy: StrategyConsoleView
    curriculum: CurriculumConsoleView
    recent_events: list[RecentEventView]
    runtime_config: dict

    def to_dict(self) -> dict:
        return {
            "dashboard": self.dashboard.to_dict(),
            "major_node_recommendations": [item.to_dict() for item in self.major_node_recommendations],
            "review_queue": self.review_queue.to_dict(),
            "review_consensus": self.review_consensus,
            "active_learning": self.active_learning.to_dict(),
            "reward_drift": {
                "total": self.reward_drift.total,
                "review_or_block": self.reward_drift.review_or_block,
                "approve": self.reward_drift.approve,
                "drift_index": self.reward_drift.drift_index,
            },
            "cost": {
                "total_iterations": self.cost.total_iterations,
                "auto_evaluation_cost": self.cost.auto_evaluation_cost,
                "human_review_cost": self.cost.human_review_cost,
                "total_cost": self.cost.total_cost,
            },
            "policy": self.policy.to_dict(),
            "strategy": self.strategy.to_dict(),
            "curriculum": self.curriculum.to_dict(),
            "recent_events": [item.to_dict() for item in self.recent_events],
            "runtime_config": self.runtime_config,
        }


def save_decision_console(console: DecisionConsole, path: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(console.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
