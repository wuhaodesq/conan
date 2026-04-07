from __future__ import annotations

from dataclasses import dataclass, field

from .active_learning import ActiveLearningCandidate, select_uncertain_samples
from .curriculum import CurriculumAdvanceRecord, CurriculumManager
from .evaluation import AutoEvaluator
from .experiment import ExperimentTracker
from .failure_analysis import FailureTaxonomy, analyze_failures
from .generation import TaskGenerator
from .human_review import HumanReviewItem, HumanReviewQueue
from .metrics import DecisionMetrics, summarize_decisions
from .pipeline import Decision, DecisionNode, IterationReport, TrainingPipeline
from .review_router import RoutedReviewBatch, route_review_items
from .state import EngineStateSnapshot
from .strategy import StrategyManager, StrategySwitchRecord
from .triggers import NodeTriggerRecommendation, recommend_major_nodes
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
    pipeline: TrainingPipeline = field(default_factory=TrainingPipeline)
    review_queue: HumanReviewQueue = field(default_factory=HumanReviewQueue)
    strategy_manager: StrategyManager = field(default_factory=StrategyManager)
    curriculum_manager: CurriculumManager = field(default_factory=CurriculumManager)
    tracker: ExperimentTracker = field(default_factory=ExperimentTracker)

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
        recommendations = recommend_major_nodes(self.summarize_metrics())
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
