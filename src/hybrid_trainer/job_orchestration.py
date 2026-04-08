from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class OrchestratedJob:
    job_id: str
    kind: str
    service: str
    status: str
    payload: dict
    dependencies: list[str]
    queued_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict | None = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "service": self.service,
            "status": self.status,
            "payload": self.payload,
            "dependencies": list(self.dependencies),
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class JobOrchestrator:
    jobs: list[OrchestratedJob] = field(default_factory=list)
    _counter: int = 0

    def run_job(
        self,
        kind: str,
        service: str,
        payload: dict,
        runner: Callable[[], tuple[T, dict]],
        dependencies: list[str] | None = None,
    ) -> tuple[T, str]:
        self._counter += 1
        job = OrchestratedJob(
            job_id=f"job-{self._counter}",
            kind=kind,
            service=service,
            status="queued",
            payload=payload,
            dependencies=list(dependencies or []),
            queued_at=_timestamp(),
        )
        self.jobs.append(job)
        job.status = "running"
        job.started_at = _timestamp()

        try:
            value, result_payload = runner()
        except Exception as exc:
            job.status = "failed"
            job.completed_at = _timestamp()
            job.error = str(exc)
            raise

        job.status = "completed"
        job.completed_at = _timestamp()
        job.result = result_payload
        return value, job.job_id

    def summary(self) -> dict:
        return {
            "total_jobs": len(self.jobs),
            "completed_jobs": sum(1 for item in self.jobs if item.status == "completed"),
            "failed_jobs": sum(1 for item in self.jobs if item.status == "failed"),
            "queued_jobs": sum(1 for item in self.jobs if item.status == "queued"),
            "running_jobs": sum(1 for item in self.jobs if item.status == "running"),
            "kinds": sorted({item.kind for item in self.jobs}),
            "services": sorted({item.service for item in self.jobs}),
        }

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "jobs": [item.to_dict() for item in self.jobs],
        }


def save_job_orchestrator(orchestrator: JobOrchestrator, path: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(orchestrator.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
