from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from .command_backend import run_json_command
from .metrics import DecisionMetrics
from .strategy import TrainingStrategy


@dataclass(slots=True)
class TrainingExecutionRequest:
    strategy: TrainingStrategy
    metrics: DecisionMetrics
    curriculum_stage: str
    policy_version: str

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "metrics": self.metrics.to_dict(),
            "curriculum_stage": self.curriculum_stage,
            "policy_version": self.policy_version,
        }


@dataclass(slots=True)
class TrainingExecutionResult:
    strategy: TrainingStrategy
    status: str
    objective: str
    input_samples: int
    training_steps: int
    epochs: int
    curriculum_stage: str
    policy_version: str
    artifact_path: str = ""

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "status": self.status,
            "objective": self.objective,
            "input_samples": self.input_samples,
            "training_steps": self.training_steps,
            "epochs": self.epochs,
            "curriculum_stage": self.curriculum_stage,
            "policy_version": self.policy_version,
            "artifact_path": self.artifact_path,
        }


class TrainingExecutor(Protocol):
    def execute(
        self,
        request: TrainingExecutionRequest,
        output_path: str = "",
    ) -> "TrainingExecutionResult":
        ...


class SimulatedTrainingExecutor:
    """Small deterministic executor used to wire training runs into artifacts and logs."""

    def execute(
        self,
        request: TrainingExecutionRequest,
        output_path: str = "",
    ) -> TrainingExecutionResult:
        input_samples, training_steps, epochs, objective = self._plan(request)
        result = TrainingExecutionResult(
            strategy=request.strategy,
            status="completed",
            objective=objective,
            input_samples=input_samples,
            training_steps=training_steps,
            epochs=epochs,
            curriculum_stage=request.curriculum_stage,
            policy_version=request.policy_version,
            artifact_path=output_path,
        )
        if output_path:
            save_training_execution_result(result, output_path)
        return result

    def _plan(self, request: TrainingExecutionRequest) -> tuple[int, int, int, str]:
        metrics = request.metrics
        if request.strategy == TrainingStrategy.SFT:
            input_samples = max(metrics.approve + metrics.review, 1)
            return input_samples, input_samples * 20, 2, "supervised_finetuning"

        if request.strategy == TrainingStrategy.RL:
            input_samples = max(metrics.total, 1)
            return input_samples, input_samples * 25, 3, "policy_optimization"

        input_samples = max(metrics.approve + metrics.review, 1)
        return input_samples, input_samples * 18, 2, "preference_optimization"


class CommandTrainingExecutor:
    """Adapter that delegates training execution to an external JSON-speaking command."""

    def __init__(self, command: str, timeout_seconds: int = 120, service_name: str = "") -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.service_name = service_name or type(self).__name__

    def execute(
        self,
        request: TrainingExecutionRequest,
        output_path: str = "",
    ) -> TrainingExecutionResult:
        response = run_json_command(
            self.command,
            payload={
                "request": request.to_dict(),
                "output_path": output_path,
            },
            timeout_seconds=self.timeout_seconds,
        )

        result = TrainingExecutionResult(
            strategy=TrainingStrategy(str(response.get("strategy", request.strategy.value))),
            status=str(response.get("status", "completed")),
            objective=str(response["objective"]),
            input_samples=int(response["input_samples"]),
            training_steps=int(response["training_steps"]),
            epochs=int(response["epochs"]),
            curriculum_stage=str(response.get("curriculum_stage", request.curriculum_stage)),
            policy_version=str(response.get("policy_version", request.policy_version)),
            artifact_path=str(response.get("artifact_path", output_path)),
        )
        if output_path:
            save_training_execution_result(result, output_path)
        return result


def save_training_execution_result(result: TrainingExecutionResult, path: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
