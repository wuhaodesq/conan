from __future__ import annotations

from dataclasses import dataclass

from .generation import TaskSample


@dataclass(slots=True)
class EvaluationResult:
    task_id: str
    score: float
    passed: bool


class AutoEvaluator:
    """MVP evaluator with deterministic scoring for stable tests."""

    def __init__(self, pass_threshold: float = 0.8) -> None:
        self.pass_threshold = pass_threshold

    def evaluate(self, sample: TaskSample) -> EvaluationResult:
        suffix = int(sample.task_id.split("-")[-1])
        score = min(1.0, max(0.0, suffix / 10))
        return EvaluationResult(
            task_id=sample.task_id,
            score=score,
            passed=score >= self.pass_threshold,
        )
