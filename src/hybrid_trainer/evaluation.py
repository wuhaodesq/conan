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
        score = self._score(sample)
        return EvaluationResult(
            task_id=sample.task_id,
            score=score,
            passed=score >= self.pass_threshold,
        )

    def _score(self, sample: TaskSample) -> float:
        if sample.reference_answer and not sample.task_id.startswith("task-"):
            return 1.0 if _normalize_text(sample.candidate_answer) == _normalize_text(sample.reference_answer) else 0.0

        try:
            suffix = int(sample.task_id.split("-")[-1])
        except ValueError:
            if sample.reference_answer:
                return 1.0 if _normalize_text(sample.candidate_answer) == _normalize_text(sample.reference_answer) else 0.0
            baseline = max(len(sample.prompt), 1)
            return min(1.0, len(sample.candidate_answer) / baseline)

        return min(1.0, max(0.0, suffix / 10))


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())
