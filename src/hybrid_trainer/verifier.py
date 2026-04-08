from __future__ import annotations

from dataclasses import dataclass

from .generation import TaskSample


@dataclass(slots=True)
class VerifierResult:
    verifier_score: float
    delta: float
    requires_review: bool


class SimpleVerifier:
    """Deterministic verifier used to detect evaluator drift in MVP."""

    def __init__(self, review_delta_threshold: float = 0.3) -> None:
        self.review_delta_threshold = review_delta_threshold

    def verify(self, sample: TaskSample, auto_score: float) -> VerifierResult:
        verifier_score = (len(sample.candidate_answer) % 10) / 10
        delta = abs(verifier_score - auto_score)
        return VerifierResult(
            verifier_score=verifier_score,
            delta=delta,
            requires_review=delta >= self.review_delta_threshold,
        )


class ReferenceAnswerVerifier(SimpleVerifier):
    """Verifier backed by task-level reference answers."""

    def verify(self, sample: TaskSample, auto_score: float) -> VerifierResult:
        if not sample.reference_answer:
            return VerifierResult(
                verifier_score=auto_score,
                delta=0.0,
                requires_review=False,
            )

        verifier_score = 1.0 if _normalize_text(sample.candidate_answer) == _normalize_text(sample.reference_answer) else 0.0
        delta = abs(verifier_score - auto_score)
        return VerifierResult(
            verifier_score=verifier_score,
            delta=delta,
            requires_review=delta >= self.review_delta_threshold,
        )


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())
