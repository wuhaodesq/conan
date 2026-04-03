"""Hybrid self-improvement training prototype."""

from .cli import run as run_cli
from .curriculum import CurriculumAdvanceRecord, CurriculumManager, CurriculumStage
from .engine import CycleResult, TrainingEngine
from .evaluation import AutoEvaluator, EvaluationResult
from .experiment import ExperimentEvent, ExperimentTracker
from .generation import TaskGenerator, TaskSample
from .human_review import HumanReviewDecision, HumanReviewItem, HumanReviewQueue
from .metrics import DecisionMetrics, summarize_decisions
from .reward_policy import RewardPolicy
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

__all__ = [
    "AutoEvaluator",
    "CurriculumAdvanceRecord",
    "CurriculumManager",
    "CurriculumStage",
    "CycleResult",
    "Decision",
    "DecisionMetrics",
    "DecisionNode",
    "EngineStateSnapshot",
    "EvaluationResult",
    "ExperimentEvent",
    "ExperimentTracker",
    "HumanReviewDecision",
    "HumanReviewItem",
    "HumanReviewQueue",
    "IterationReport",
    "NodeTriggerRecommendation",
    "PipelineConfig",
    "RewardPolicy",
    "StrategyManager",
    "StrategySwitchRecord",
    "TaskGenerator",
    "TaskSample",
    "TrainingEngine",
    "TrainingPipeline",
    "TrainingStrategy",
    "load_snapshot",
    "recommend_major_nodes",
    "run_cli",
    "save_snapshot",
    "summarize_decisions",
]
