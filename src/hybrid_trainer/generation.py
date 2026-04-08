from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(slots=True)
class TaskSample:
    task_id: str
    prompt: str
    candidate_answer: str
    reference_answer: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "candidate_answer": self.candidate_answer,
            "reference_answer": self.reference_answer,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "TaskSample":
        return cls(
            task_id=str(payload["task_id"]),
            prompt=str(payload["prompt"]),
            candidate_answer=str(payload.get("candidate_answer", "")),
            reference_answer=str(payload.get("reference_answer", "")),
        )


class TaskGenerator:
    """Simple deterministic generator for MVP stage."""

    def generate(self, iteration: int) -> TaskSample:
        return TaskSample(
            task_id=f"task-{iteration}",
            prompt=f"Solve task {iteration}",
            candidate_answer=f"answer-{iteration}",
        )


class DatasetTaskGenerator(TaskGenerator):
    """Task generator backed by JSON/JSONL task corpora."""

    def __init__(self, tasks: list[TaskSample]) -> None:
        if not tasks:
            raise ValueError("tasks must not be empty")
        self.tasks = tasks

    def generate(self, iteration: int) -> TaskSample:
        template = self.tasks[(iteration - 1) % len(self.tasks)]
        return TaskSample(
            task_id=template.task_id,
            prompt=template.prompt,
            candidate_answer=template.candidate_answer,
            reference_answer=template.reference_answer,
        )

    @classmethod
    def from_file(cls, path: str) -> "DatasetTaskGenerator":
        return cls(load_task_samples(path))


def load_task_samples(path: str) -> list[TaskSample]:
    source = Path(path)
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if source.suffix.lower() == ".jsonl":
        payloads = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        payloads = payload.get("items", payload) if isinstance(payload, dict) else payload

    return [TaskSample.from_dict(item) for item in payloads]
