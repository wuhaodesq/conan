from __future__ import annotations

from dataclasses import dataclass, field

from .evaluation import AutoEvaluator
from .generation import TaskGenerator
from .human_review import HumanReviewItem, HumanReviewQueue
from .metrics import DecisionMetrics, summarize_decisions
from .pipeline import Decision, DecisionNode, IterationReport, TrainingPipeline
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

    def run_cycle(self, iteration: int, node: DecisionNode) -> CycleResult:
        sample = self.generator.generate(iteration)
        result = self.evaluator.evaluate(sample)
        report = self.pipeline.run_iteration(iteration, result.score, node)

        if report.decision in (Decision.REVIEW, Decision.BLOCK):
            self.review_queue.enqueue(
                HumanReviewItem(
                    iteration=iteration,
                    node=node,
                    auto_score=result.score,
                    auto_decision=report.decision,
                )
            )

        return CycleResult(iteration=iteration, score=result.score, decision_report=report)

    def run_cycles(self, start: int, end: int, node: DecisionNode) -> list[CycleResult]:
        return [self.run_cycle(i, node) for i in range(start, end + 1)]

    def summarize_metrics(self) -> DecisionMetrics:
        return summarize_decisions(self.pipeline.history)

    def recommend_nodes(self) -> list[NodeTriggerRecommendation]:
        return recommend_major_nodes(self.summarize_metrics())

    def maybe_switch_strategy(self) -> StrategySwitchRecord | None:
        return self.strategy_manager.maybe_switch(self.summarize_metrics())
