"""Hybrid self-improvement training prototype."""

from .active_learning import ActiveLearningCandidate, select_uncertain_samples
from .cli import run as run_cli
from .cost import CostReport, estimate_cost
from .curriculum import CurriculumAdvanceRecord, CurriculumManager, CurriculumStage
from .engine import CycleResult, TrainingEngine
from .evaluation import AutoEvaluator, EvaluationResult
from .experiment import ExperimentEvent, ExperimentTracker
from .failure_analysis import FailureTaxonomy, analyze_failures
from .generation import TaskGenerator, TaskSample
from .human_review import HumanReviewDecision, HumanReviewItem, HumanReviewQueue
from .metrics import DecisionMetrics, summarize_decisions
from .reward_policy import RewardPolicy
from .reward_drift import RewardDriftReport, compute_reward_drift
from .search import PathCandidate, select_best_path
from .report import DecisionDashboard, build_dashboard
from .review_router import RoutedReviewBatch, route_review_items
from .policy_registry import PolicyRegistry, PolicyVersionRecord
from .pipeline import (
    Decision,
    DecisionNode,
    IterationReport,
    PipelineConfig,
    TrainingPipeline,
)
from .state import EngineStateSnapshot, load_snapshot, save_snapshot
from .strategy import StrategyManager, StrategySwitchRecord, TrainingStrategy
from .triggers import NodeTriggerRecommendation, recommend_major_nodes
from .verifier import SimpleVerifier, VerifierResult

__all__ = [
    "ActiveLearningCandidate",
    "AutoEvaluator",
    "CostReport",
    "CurriculumAdvanceRecord",
    "CurriculumManager",
    "CurriculumStage",
    "CycleResult",
    "Decision",
    "DecisionDashboard",
    "DecisionMetrics",
    "DecisionNode",
    "EngineStateSnapshot",
    "EvaluationResult",
    "ExperimentEvent",
    "ExperimentTracker",
    "FailureTaxonomy",
    "HumanReviewDecision",
    "HumanReviewItem",
    "HumanReviewQueue",
    "IterationReport",
    "NodeTriggerRecommendation",
    "PathCandidate",
    "PipelineConfig",
    "PolicyRegistry",
    "PolicyVersionRecord",
    "RewardDriftReport",
    "RewardPolicy",
    "RoutedReviewBatch",
    "SimpleVerifier",
    "StrategyManager",
    "StrategySwitchRecord",
    "TaskGenerator",
    "TaskSample",
    "TrainingEngine",
    "TrainingPipeline",
    "TrainingStrategy",
    "VerifierResult",
    "analyze_failures",
    "build_dashboard",
    "compute_reward_drift",
    "estimate_cost",
    "load_snapshot",
    "recommend_major_nodes",
    "route_review_items",
    "run_cli",
    "save_snapshot",
    "select_best_path",
    "select_uncertain_samples",
    "summarize_decisions",
]
