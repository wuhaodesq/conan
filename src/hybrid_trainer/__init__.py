"""Hybrid self-improvement training prototype."""

from .active_learning import ActiveLearningCandidate, select_uncertain_samples
from .cli import run as run_cli
from .command_backend import CommandBackendError
from .cost import CostReport, estimate_cost
from .curriculum import CurriculumAdvanceRecord, CurriculumManager, CurriculumStage
from .decision_console import DecisionConsole, save_decision_console
from .engine import CycleResult, TrainingEngine
from .evaluation import AutoEvaluator, CommandAutoEvaluator, EvaluationResult, Evaluator
from .experiment import ExperimentEvent, ExperimentTracker
from .failure_analysis import FailureTaxonomy, analyze_failures
from .generation import CommandTaskGenerator, DatasetTaskGenerator, TaskGenerator, TaskSample, load_task_samples
from .human_review import (
    HumanReviewDecision,
    HumanReviewItem,
    HumanReviewQueue,
    load_review_decisions,
    save_review_batch,
    save_review_decisions,
)
from .job_orchestration import JobOrchestrator, OrchestratedJob, save_job_orchestrator
from .metrics import DecisionMetrics, summarize_decisions
from .model_service import ModelServiceConfig, ModelServiceRegistry
from .runtime_config import RuntimeConfig, load_runtime_config
from .reward_policy import RewardPolicy
from .reward_drift import RewardDriftReport, compute_reward_drift
from .search import PathCandidate, select_best_path
from .report import DecisionDashboard, build_dashboard
from .review_audit import append_review_audit_event, create_review_audit_event, load_review_audit_events
from .review_consensus import ReviewConsensusRecord, build_review_consensus, save_review_consensus
from .review_identity import (
    IdentityProvider,
    OidcAuthorizationCodeIdentityProvider,
    OidcPendingLogin,
    OidcSessionRecord,
    IntrospectionIdentityProvider,
    ReviewIdentity,
    StaticIdentityProvider,
    build_identity_provider_from_file,
)
from .review_permissions import ReviewPermissionPolicy, ReviewRolePolicy
from .review_router import RoutedReviewBatch, route_review_items, score_review_risk
from .review_server import build_review_server, serve_review_server
from .review_session import (
    ReviewSession,
    ReviewerSubmission,
    export_review_session_decisions,
    load_review_decision_payload,
    load_review_session,
    save_review_session,
)
from .review_store import (
    FileReviewStore,
    ObjectStorageReviewStore,
    PostgresReviewStore,
    ReviewStore,
    SqliteReviewStore,
    build_review_store,
)
from .review_web import render_review_workbench_html, save_review_workbench_html
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
    CommandTrainingExecutor,
    SimulatedTrainingExecutor,
    TrainingExecutor,
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
    "CommandAutoEvaluator",
    "CommandBackendError",
    "CommandTaskGenerator",
    "CommandTrainingExecutor",
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
    "Evaluator",
    "ExperimentEvent",
    "ExperimentTracker",
    "FailureTaxonomy",
    "HumanReviewDecision",
    "HumanReviewItem",
    "HumanReviewQueue",
    "IdentityProvider",
    "IterationReport",
    "JobOrchestrator",
    "IntrospectionIdentityProvider",
    "OidcAuthorizationCodeIdentityProvider",
    "OidcPendingLogin",
    "OidcSessionRecord",
    "ModelServiceConfig",
    "ModelServiceRegistry",
    "NodeTriggerRecommendation",
    "OrchestratedJob",
    "PathCandidate",
    "PipelineConfig",
    "ReferenceAnswerVerifier",
    "PolicyRegistry",
    "PolicyVersionRecord",
    "ReviewConsensusRecord",
    "ReviewIdentity",
    "ReviewPermissionPolicy",
    "ReviewRolePolicy",
    "ReviewSession",
    "ReviewerSubmission",
    "RewardDriftReport",
    "RewardPolicy",
    "RoutedReviewBatch",
    "RuntimeConfig",
    "SimpleVerifier",
    "StrategyManager",
    "StrategySwitchRecord",
    "TrainingExecutionRequest",
    "TrainingExecutionResult",
    "TrainingExecutor",
    "TaskGenerator",
    "TaskSample",
    "TrainingEngine",
    "SimulatedTrainingExecutor",
    "TrainingPipeline",
    "TrainingStrategy",
    "TriggerRuleConfig",
    "VerifierResult",
    "PostgresReviewStore",
    "ObjectStorageReviewStore",
    "analyze_failures",
    "append_review_audit_event",
    "build_review_consensus",
    "build_identity_provider_from_file",
    "build_dashboard",
    "build_review_server",
    "build_review_store",
    "compute_reward_drift",
    "create_review_audit_event",
    "estimate_cost",
    "collect_review_decisions",
    "export_review_session_decisions",
    "load_review_decisions",
    "load_review_audit_events",
    "load_review_decision_payload",
    "load_runtime_config",
    "load_review_session",
    "load_snapshot",
    "load_task_samples",
    "recommend_major_nodes",
    "render_decision_console",
    "render_decision_console_html",
    "render_review_batch",
    "render_review_workbench_html",
    "route_review_items",
    "run_cli",
    "save_review_batch",
    "save_review_consensus",
    "save_review_decisions",
    "save_decision_console",
    "save_decision_console_html",
    "save_job_orchestrator",
    "save_review_session",
    "save_review_workbench_html",
    "save_snapshot",
    "save_training_execution_result",
    "score_review_risk",
    "select_best_path",
    "select_uncertain_samples",
    "serve_review_server",
    "FileReviewStore",
    "ObjectStorageReviewStore",
    "PostgresReviewStore",
    "ReviewStore",
    "SqliteReviewStore",
    "StaticIdentityProvider",
    "summarize_decisions",
]
