"""Hybrid self-improvement training prototype."""

from .engine import CycleResult, TrainingEngine
from .evaluation import AutoEvaluator, EvaluationResult
from .experiment import ExperimentEvent, ExperimentTracker
from .generation import TaskGenerator, TaskSample
from .human_review import HumanReviewDecision, HumanReviewItem, HumanReviewQueue
from .metrics import DecisionMetrics, summarize_decisions
from .pipeline import (
    Decision,
    DecisionNode,
    IterationReport,
    PipelineConfig,
    TrainingPipeline,
)
from .strategy import StrategyManager, StrategySwitchRecord, TrainingStrategy
from .triggers import NodeTriggerRecommendation, recommend_major_nodes

__all__ = [
    "AutoEvaluator",
    "CycleResult",
    "Decision",
    "DecisionMetrics",
    "DecisionNode",
    "EvaluationResult",
    "ExperimentEvent",
    "ExperimentTracker",
    "HumanReviewDecision",
    "HumanReviewItem",
    "HumanReviewQueue",
    "IterationReport",
    "NodeTriggerRecommendation",
    "PipelineConfig",
    "StrategyManager",
    "StrategySwitchRecord",
    "TaskGenerator",
    "TaskSample",
    "TrainingEngine",
    "TrainingPipeline",
    "TrainingStrategy",
    "recommend_major_nodes",
    "summarize_decisions",
]
