from __future__ import annotations

from dataclasses import dataclass

from .pipeline import IterationReport


@dataclass(slots=True)
class ActiveLearningCandidate:
    iteration: int
    score: float
    uncertainty: float


def select_uncertain_samples(
    history: list[IterationReport],
    threshold: float,
    limit: int,
) -> list[ActiveLearningCandidate]:
    if limit <= 0:
        return []

    candidates = [
        ActiveLearningCandidate(
            iteration=item.iteration,
            score=item.auto_score,
            uncertainty=abs(item.auto_score - threshold),
        )
        for item in history
    ]
    candidates.sort(key=lambda x: x.uncertainty)
    return candidates[:limit]
