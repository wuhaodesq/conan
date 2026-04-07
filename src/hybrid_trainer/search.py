from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PathCandidate:
    path_id: int
    score: float
    answer: str


def select_best_path(candidates: list[PathCandidate]) -> PathCandidate:
    if not candidates:
        raise ValueError("No candidates to select from")
    return max(candidates, key=lambda item: item.score)
