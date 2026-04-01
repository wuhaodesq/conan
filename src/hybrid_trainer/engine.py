from __future__ import annotations

from dataclasses import dataclass, field

from .evaluation import AutoEvaluator
from .generation import TaskGenerator
from .pipeline import DecisionNode, IterationReport, TrainingPipeline


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

    def run_cycle(self, iteration: int, node: DecisionNode) -> CycleResult:
        sample = self.generator.generate(iteration)
        result = self.evaluator.evaluate(sample)
        report = self.pipeline.run_iteration(iteration, result.score, node)
        return CycleResult(iteration=iteration, score=result.score, decision_report=report)
