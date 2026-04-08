from __future__ import annotations

from dataclasses import dataclass, field

from .active_learning import ActiveLearningCandidate, select_uncertain_samples
from .cost import CostReport, estimate_cost
from .curriculum import CurriculumAdvanceRecord, CurriculumManager
from .decision_console import (
    ActiveLearningConsole,
    CurriculumConsoleView,
    DecisionConsole,
    MajorNodeRecommendationView,
    PolicyConsoleView,
    PolicyVersionView,
    RecentEventView,
    ReviewQueueConsole,
    ReviewQueueItemView,
    StrategyConsoleView,
)
from .evaluation import AutoEvaluator
from .experiment import ExperimentTracker
from .failure_analysis import FailureTaxonomy, analyze_failures
from .generation import TaskGenerator, TaskSample
from .human_review import HumanReviewDecision, HumanReviewItem, HumanReviewQueue, save_review_batch
from .metrics import DecisionMetrics, summarize_decisions
from .pipeline import Decision, DecisionNode, IterationReport, TrainingPipeline
from .policy_registry import PolicyRegistry
from .report import DecisionDashboard, build_dashboard
from .reward_drift import RewardDriftReport, compute_reward_drift
from .review_router import RoutedReviewBatch, route_review_items, score_review_risk
from .runtime_config import RuntimeConfig
from .search import PathCandidate, select_best_path
from .state import EngineStateSnapshot
from .strategy import StrategyManager, StrategySwitchRecord
from .training_execution import SimulatedTrainingExecutor, TrainingExecutionRequest, TrainingExecutionResult
from .triggers import NodeTriggerRecommendation, TriggerRuleConfig, recommend_major_nodes
from .verifier import SimpleVerifier


@dataclass(slots=True)
class CycleResult:
    iteration: int
    score: float
    decision_report: IterationReport


@dataclass
class TrainingEngine:
    generator: TaskGenerator = field(default_factory=TaskGenerator)
    evaluator: AutoEvaluator = field(default_factory=AutoEvaluator)
    verifier: SimpleVerifier = field(default_factory=SimpleVerifier)
    training_executor: SimulatedTrainingExecutor = field(default_factory=SimulatedTrainingExecutor)
    pipeline: TrainingPipeline = field(default_factory=TrainingPipeline)
    review_queue: HumanReviewQueue = field(default_factory=HumanReviewQueue)
    strategy_manager: StrategyManager = field(default_factory=StrategyManager)
    curriculum_manager: CurriculumManager = field(default_factory=CurriculumManager)
    policy_registry: PolicyRegistry = field(default_factory=PolicyRegistry)
    tracker: ExperimentTracker = field(default_factory=ExperimentTracker)
    trigger_rules: TriggerRuleConfig = field(default_factory=TriggerRuleConfig)


    def __post_init__(self) -> None:
        active = self.pipeline.config.reward_policy
        if active.version not in self.policy_registry.versions:
            self.policy_registry.register(active, note="default bootstrap policy")
        if self.policy_registry.active_version is None:
            self.policy_registry.active_version = active.version

    def run_cycle(self, iteration: int, node: DecisionNode) -> CycleResult:
        sample = self.generator.generate(iteration)
        result = self.evaluator.evaluate(sample)
        report = self.pipeline.run_iteration(
            iteration,
            result.score,
            node,
            candidate_answer=sample.candidate_answer,
        )

        verifier_result = self.verifier.verify(sample, result.score)
        if verifier_result.requires_review and report.decision == Decision.APPROVE:
            report = IterationReport(
                iteration=report.iteration,
                auto_score=report.auto_score,
                node=report.node,
                decision=Decision.REVIEW,
                reason=f"Verifier 偏差 {verifier_result.delta:.2f} 超阈值，转人工复核",
            )
            self.pipeline.history[-1] = report
            self.tracker.track(
                event_type="verifier_override",
                payload={
                    "iteration": iteration,
                    "auto_score": result.score,
                    "verifier_score": verifier_result.verifier_score,
                    "delta": verifier_result.delta,
                },
            )

        if report.decision in (Decision.REVIEW, Decision.BLOCK):
            self.review_queue.enqueue(
                HumanReviewItem(
                    iteration=iteration,
                    node=node,
                    auto_score=result.score,
                    auto_decision=report.decision,
                )
            )

        cycle_result = CycleResult(iteration=iteration, score=result.score, decision_report=report)
        self.tracker.track(
            event_type="cycle_completed",
            payload={
                "iteration": iteration,
                "score": result.score,
                "node": node.value,
                "decision": report.decision.value,
                "curriculum_stage": self.curriculum_manager.current_stage.name,
            },
        )
        return cycle_result


    def run_multi_path_cycle(self, iteration: int, node: DecisionNode, num_paths: int = 3) -> CycleResult:
        if num_paths <= 0:
            raise ValueError("num_paths must be positive")

        base = self.generator.generate(iteration)
        candidates: list[PathCandidate] = []
        for idx in range(num_paths):
            sample = TaskSample(
                task_id=base.task_id,
                prompt=base.prompt,
                candidate_answer=f"{base.candidate_answer}-path-{idx}",
            )
            result = self.evaluator.evaluate(sample)
            candidates.append(PathCandidate(path_id=idx, score=result.score, answer=sample.candidate_answer))

        best = select_best_path(candidates)
        self.tracker.track(
            event_type="multi_path_selected",
            payload={"iteration": iteration, "path_id": best.path_id, "score": best.score, "num_paths": num_paths},
        )

        # Reuse single-path flow with best candidate score routed through pipeline.
        report = self.pipeline.run_iteration(iteration, best.score, node, candidate_answer=best.answer)
        if report.decision in (Decision.REVIEW, Decision.BLOCK):
            self.review_queue.enqueue(
                HumanReviewItem(
                    iteration=iteration,
                    node=node,
                    auto_score=best.score,
                    auto_decision=report.decision,
                )
            )
        return CycleResult(iteration=iteration, score=best.score, decision_report=report)

    def run_cycles(self, start: int, end: int, node: DecisionNode) -> list[CycleResult]:
        return [self.run_cycle(i, node) for i in range(start, end + 1)]

    def summarize_metrics(self) -> DecisionMetrics:
        metrics = summarize_decisions(self.pipeline.history)
        self.tracker.track(
            event_type="metrics_summarized",
            payload={
                "total": metrics.total,
                "approve": metrics.approve,
                "review": metrics.review,
                "block": metrics.block,
            },
        )
        return metrics

    def recommend_nodes(self) -> list[NodeTriggerRecommendation]:
        recommendations = recommend_major_nodes(self.summarize_metrics(), self.trigger_rules)
        self.tracker.track(
            event_type="nodes_recommended",
            payload={"nodes": [item.node.value for item in recommendations]},
        )
        return recommendations

    def maybe_switch_strategy(self) -> StrategySwitchRecord | None:
        switch = self.strategy_manager.maybe_switch(self.summarize_metrics())
        if switch is not None:
            self.tracker.track(
                event_type="strategy_switched",
                payload={
                    "from": switch.from_strategy.value,
                    "to": switch.to_strategy.value,
                    "reason": switch.reason,
                },
            )
        return switch

    def maybe_advance_curriculum(self) -> CurriculumAdvanceRecord | None:
        record = self.curriculum_manager.maybe_advance(self.summarize_metrics())
        if record is not None:
            self.tracker.track(
                event_type="curriculum_advanced",
                payload={
                    "from": record.from_stage,
                    "to": record.to_stage,
                    "reason": record.reason,
                },
            )
        return record

    def snapshot_state(self) -> EngineStateSnapshot:
        return EngineStateSnapshot(
            strategy=self.strategy_manager.current,
            curriculum_index=self.curriculum_manager.current_index,
            history_count=len(self.pipeline.history),
            pending_reviews=len(self.review_queue.pending),
        )

    def restore_state(self, snapshot: EngineStateSnapshot) -> None:
        self.strategy_manager.current = snapshot.strategy
        self.curriculum_manager.current_index = min(snapshot.curriculum_index, len(self.curriculum_manager.stages) - 1)

    def get_review_batch(self, budget: int) -> RoutedReviewBatch:
        batch = route_review_items(self.review_queue.pending, budget)
        self.tracker.track(
            event_type="review_batch_routed",
            payload={
                "budget": budget,
                "selected": [item.iteration for item in batch.items],
            },
        )
        return batch

    def export_review_batch(self, path: str, budget: int) -> None:
        batch = self.get_review_batch(budget)
        save_review_batch(batch.items, path, budget=batch.budget)
        self.tracker.track(
            event_type="review_batch_exported",
            payload={
                "path": path,
                "budget": budget,
                "selected": [item.iteration for item in batch.items],
            },
        )

    def apply_review_decisions(self, decisions: list[HumanReviewDecision]) -> list[HumanReviewDecision]:
        resolved = [
            self.review_queue.resolve(
                iteration=item.iteration,
                final_decision=item.final_decision,
                reviewer=item.reviewer,
                note=item.note,
            )
            for item in decisions
        ]
        self.tracker.track(
            event_type="review_decisions_applied",
            payload={
                "iterations": [item.iteration for item in resolved],
                "final_decisions": [item.final_decision.value for item in resolved],
                "count": len(resolved),
            },
        )
        return resolved

    def collect_active_learning_candidates(self, limit: int) -> list[ActiveLearningCandidate]:
        threshold = self.pipeline.config.reward_policy.approve_threshold
        candidates = select_uncertain_samples(self.pipeline.history, threshold=threshold, limit=limit)
        self.tracker.track(
            event_type="active_learning_selected",
            payload={
                "limit": limit,
                "iterations": [item.iteration for item in candidates],
            },
        )
        return candidates


    def diagnose_failures(self) -> FailureTaxonomy:
        taxonomy = analyze_failures(self.pipeline.history)
        self.tracker.track(
            event_type="failure_diagnosed",
            payload={
                "low_score_block": taxonomy.low_score_block,
                "policy_block": taxonomy.policy_block,
                "verifier_override_review": taxonomy.verifier_override_review,
                "generic_review": taxonomy.generic_review,
            },
        )
        return taxonomy


    def generate_dashboard(self) -> DecisionDashboard:
        metrics = self.summarize_metrics()
        failures = self.diagnose_failures()
        recommendations = recommend_major_nodes(metrics, self.trigger_rules)
        dashboard = build_dashboard(metrics, failures, recommendations)
        self.tracker.track(
            event_type="dashboard_generated",
            payload=dashboard.to_dict(),
        )
        return dashboard

    def generate_decision_console(
        self,
        review_budget: int = 5,
        active_learning_limit: int = 5,
        recent_event_limit: int = 10,
    ) -> DecisionConsole:
        metrics = summarize_decisions(self.pipeline.history)
        failures = analyze_failures(self.pipeline.history)
        recommendations = recommend_major_nodes(metrics, self.trigger_rules)
        dashboard = build_dashboard(metrics, failures, recommendations)

        review_batch = route_review_items(self.review_queue.pending, budget=review_budget)
        review_queue = ReviewQueueConsole(
            pending_count=len(self.review_queue.pending),
            resolved_count=len(self.review_queue.resolved),
            budget=review_batch.budget,
            prioritized_items=[
                ReviewQueueItemView(
                    iteration=item.iteration,
                    node=item.node.value,
                    auto_score=item.auto_score,
                    auto_decision=item.auto_decision.value,
                    risk_score=score_review_risk(item),
                )
                for item in review_batch.items
            ],
            recent_resolutions=[
                item.to_dict()
                for item in self.review_queue.resolved[-5:]
            ],
        )

        threshold = self.pipeline.config.reward_policy.approve_threshold
        active_learning = ActiveLearningConsole(
            threshold=threshold,
            limit=active_learning_limit,
            candidates=select_uncertain_samples(
                self.pipeline.history,
                threshold=threshold,
                limit=active_learning_limit,
            ),
        )

        policy = PolicyConsoleView(
            active_version=self.policy_registry.active_version,
            available_versions=[
                PolicyVersionView(
                    version=record.version,
                    note=record.note,
                    is_active=record.version == self.policy_registry.active_version,
                    policy=record.policy.to_dict(),
                )
                for record in self.policy_registry.versions.values()
            ],
        )

        recommended_strategy, strategy_reason = self.strategy_manager.recommend(metrics)
        next_stage = None
        next_stage_min_approve_ratio = None
        if self.curriculum_manager.current_index < len(self.curriculum_manager.stages) - 1:
            upcoming_stage = self.curriculum_manager.stages[self.curriculum_manager.current_index + 1]
            next_stage = upcoming_stage.name
            next_stage_min_approve_ratio = upcoming_stage.min_approve_ratio

        recent_events = self.tracker.events[-recent_event_limit:] if recent_event_limit > 0 else []
        console = DecisionConsole(
            dashboard=dashboard,
            major_node_recommendations=[
                MajorNodeRecommendationView(node=item.node.value, reason=item.reason)
                for item in recommendations
            ],
            review_queue=review_queue,
            active_learning=active_learning,
            reward_drift=compute_reward_drift(self.pipeline.history),
            cost=estimate_cost(metrics),
            policy=policy,
            strategy=StrategyConsoleView(
                current=self.strategy_manager.current.value,
                recommended=recommended_strategy.value,
                reason=strategy_reason,
                history=list(self.strategy_manager.history),
            ),
            curriculum=CurriculumConsoleView(
                current_stage=self.curriculum_manager.current_stage.name,
                next_stage=next_stage,
                next_stage_min_approve_ratio=next_stage_min_approve_ratio,
                history=[
                    {
                        "from_stage": item.from_stage,
                        "to_stage": item.to_stage,
                        "reason": item.reason,
                    }
                    for item in self.curriculum_manager.history
                ],
            ),
            recent_events=[
                RecentEventView(
                    event_type=item.event_type,
                    timestamp=item.timestamp,
                    payload=item.payload,
                )
                for item in recent_events
            ],
            runtime_config=RuntimeConfig(
                reward_policy=self.pipeline.config.reward_policy,
                trigger_rules=self.trigger_rules,
            ).to_dict(),
        )
        self.tracker.track(
            event_type="decision_console_generated",
            payload={
                "review_budget": review_budget,
                "active_learning_limit": active_learning_limit,
                "recent_event_limit": recent_event_limit,
                "pending_reviews": len(self.review_queue.pending),
            },
        )
        return console


    def analyze_reward_drift(self) -> RewardDriftReport:
        report = compute_reward_drift(self.pipeline.history)
        self.tracker.track(
            event_type="reward_drift_analyzed",
            payload={
                "total": report.total,
                "approve": report.approve,
                "review_or_block": report.review_or_block,
                "drift_index": report.drift_index,
            },
        )
        return report


    def analyze_cost(self) -> CostReport:
        cost = estimate_cost(self.summarize_metrics())
        self.tracker.track(
            event_type="cost_analyzed",
            payload={
                "total_iterations": cost.total_iterations,
                "auto_evaluation_cost": cost.auto_evaluation_cost,
                "human_review_cost": cost.human_review_cost,
                "total_cost": cost.total_cost,
            },
        )
        return cost

    def execute_training(
        self,
        strategy: TrainingStrategy | None = None,
        output_path: str = "",
    ) -> TrainingExecutionResult:
        metrics = summarize_decisions(self.pipeline.history)
        target_strategy = strategy or self.strategy_manager.current
        request = TrainingExecutionRequest(
            strategy=target_strategy,
            metrics=metrics,
            curriculum_stage=self.curriculum_manager.current_stage.name,
            policy_version=self.pipeline.config.reward_policy.version,
        )
        self.tracker.track(
            event_type="training_execution_started",
            payload={
                "strategy": request.strategy.value,
                "curriculum_stage": request.curriculum_stage,
                "policy_version": request.policy_version,
                "total_samples": metrics.total,
            },
        )
        result = self.training_executor.execute(request, output_path=output_path)
        self.tracker.track(
            event_type="training_execution_completed",
            payload=result.to_dict(),
        )
        return result


    def apply_policy_version(self, version: str) -> None:
        policy = self.policy_registry.activate(version)
        self.pipeline.update_reward_policy(policy)
        self.tracker.track(
            event_type="policy_activated",
            payload={"version": version},
        )


    def register_policy(self, note: str = "") -> None:
        policy = self.pipeline.config.reward_policy
        self.policy_registry.register(policy, note=note)
        self.tracker.track(
            event_type="policy_registered",
            payload={"version": policy.version, "note": note},
        )
