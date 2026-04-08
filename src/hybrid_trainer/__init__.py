"""Hybrid self-improvement training prototype."""

from .active_learning import ActiveLearningCandidate, select_uncertain_samples
from .cli import run as run_cli
from .cost import CostReport, estimate_cost
from .curriculum import CurriculumAdvanceRecord, CurriculumManager, CurriculumStage
from .decision_console import DecisionConsole, save_decision_console
from .engine import CycleResult, TrainingEngine
from .evaluation import AutoEvaluator, EvaluationResult
from .experiment import ExperimentEvent, ExperimentTracker
from .failure_analysis import FailureTaxonomy, analyze_failures
from .generation import DatasetTaskGenerator, TaskGenerator, TaskSample, load_task_samples
from .human_review import (
    HumanReviewDecision,
    HumanReviewItem,
    HumanReviewQueue,
    load_review_decisions,
    save_review_batch,
    save_review_decisions,
)
from .metrics import DecisionMetrics, summarize_decisions
from .runtime_config import RuntimeConfig, load_runtime_config
from .reward_policy import RewardPolicy
from .reward_drift import RewardDriftReport, compute_reward_drift
from .search import PathCandidate, select_best_path
from .report import DecisionDashboard, build_dashboard
from .review_router import RoutedReviewBatch, route_review_items, score_review_risk
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
from .terminal_ui import collect_review_decisions, render_decision_console, render_review_batch
from .training_execution import (
    SimulatedTrainingExecutor,
    TrainingExecutionRequest,
    TrainingExecutionResult,
    save_training_execution_result,
)
from .triggers import NodeTriggerRecommendation, TriggerRuleConfig, recommend_major_nodes
from .verifier import ReferenceAnswerVerifier, SimpleVerifier, VerifierResult
from .web_console import render_decision_console_html, save_decision_console_html

__all__ = [
    "ActiveLearningCandidate",
    "AutoEvaluator",
    "CostReport",
    "CurriculumAdvanceRecord",
    "CurriculumManager",
    "CurriculumStage",
    "CycleResult",
    "DecisionConsole",
    "Decision",
    "DecisionDashboard",
    "DecisionMetrics",
    "DecisionNode",
    "DatasetTaskGenerator",
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
    "ReferenceAnswerVerifier",
    "PolicyRegistry",
    "PolicyVersionRecord",
    "RewardDriftReport",
    "RewardPolicy",
    "RoutedReviewBatch",
    "RuntimeConfig",
    "SimpleVerifier",
    "StrategyManager",
    "StrategySwitchRecord",
    "TrainingExecutionRequest",
    "TrainingExecutionResult",
    "TaskGenerator",
    "TaskSample",
    "TrainingEngine",
    "SimulatedTrainingExecutor",
    "TrainingPipeline",
    "TrainingStrategy",
    "TriggerRuleConfig",
    "VerifierResult",
    "analyze_failures",
    "build_dashboard",
    "compute_reward_drift",
    "estimate_cost",
    "collect_review_decisions",
    "load_review_decisions",
    "load_runtime_config",
    "load_snapshot",
    "load_task_samples",
    "recommend_major_nodes",
    "render_decision_console",
    "render_decision_console_html",
    "render_review_batch",
    "route_review_items",
    "run_cli",
    "save_review_batch",
    "save_review_decisions",
    "save_decision_console",
    "save_decision_console_html",
    "save_snapshot",
    "save_training_execution_result",
    "score_review_risk",
    "select_best_path",
    "select_uncertain_samples",
    "summarize_decisions",
]
