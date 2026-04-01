from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TaskSample:
    task_id: str
    prompt: str
    candidate_answer: str


class TaskGenerator:
    """Simple deterministic generator for MVP stage."""

    def generate(self, iteration: int) -> TaskSample:
        return TaskSample(
            task_id=f"task-{iteration}",
            prompt=f"Solve task {iteration}",
            candidate_answer=f"answer-{iteration}",
        )
