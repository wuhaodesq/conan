from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .command_backend import run_json_command
from .generation import TaskSample


@dataclass(slots=True)
class EvaluationResult:
    task_id: str
    score: float
    passed: bool

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "score": self.score,
            "passed": self.passed,
        }


class Evaluator(Protocol):
    def evaluate(self, sample: TaskSample) -> EvaluationResult:
        ...


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


class CommandAutoEvaluator(AutoEvaluator):
    """Adapter that delegates scoring to an external JSON-speaking command."""

    def __init__(
        self,
        command: str,
        pass_threshold: float = 0.8,
        timeout_seconds: int = 30,
        service_name: str = "",
    ) -> None:
        super().__init__(pass_threshold=pass_threshold)
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.service_name = service_name or type(self).__name__

    def evaluate(self, sample: TaskSample) -> EvaluationResult:
        response = run_json_command(
            self.command,
            payload={
                "task": sample.to_dict(),
                "pass_threshold": self.pass_threshold,
            },
            timeout_seconds=self.timeout_seconds,
        )
        score = float(response["score"])
        if score < 0.0 or score > 1.0:
            raise ValueError("external evaluator score must be within [0, 1]")

        passed = _coerce_optional_bool(response.get("passed"), default=score >= self.pass_threshold)
        return EvaluationResult(
            task_id=str(response.get("task_id", sample.task_id)),
            score=score,
            passed=passed,
        )


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _coerce_optional_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise ValueError("external evaluator returned an invalid passed flag")
