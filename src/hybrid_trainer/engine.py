from __future__ import annotations

from dataclasses import dataclass, field

from .curriculum import CurriculumAdvanceRecord, CurriculumManager
from .evaluation import AutoEvaluator
from .experiment import ExperimentTracker
from .generation import TaskGenerator
from .human_review import HumanReviewItem, HumanReviewQueue
from .metrics import DecisionMetrics, summarize_decisions
from .pipeline import Decision, DecisionNode, IterationReport, TrainingPipeline
from .state import EngineStateSnapshot
from .strategy import StrategyManager, StrategySwitchRecord
from .triggers import NodeTriggerRecommendation, recommend_major_nodes


@dataclass(slots=True)
class CycleResult:
    iteration: int
    score: float
    decision_report: IterationReport


@dataclass
class TrainingEngine:
    generator: TaskGenerator = field(default_factory=TaskGenerator)
    evaluator: AutoEvaluator = field(default_factory=AutoEvaluator)
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
