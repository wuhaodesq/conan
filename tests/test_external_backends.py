import json
import sys
import textwrap

from hybrid_trainer.cli import run
from hybrid_trainer.evaluation import CommandAutoEvaluator
from hybrid_trainer.generation import TaskSample
from hybrid_trainer.metrics import DecisionMetrics
from hybrid_trainer.strategy import TrainingStrategy
from hybrid_trainer.training_execution import CommandTrainingExecutor, TrainingExecutionRequest


def _write_script(path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def test_command_auto_evaluator_can_delegate_to_external_script(tmp_path) -> None:
    script = tmp_path / "external_evaluator.py"
    _write_script(
        script,
        """
        import json
        import sys

        payload = json.load(sys.stdin)
        task = payload["task"]
        score = 1.0 if task["candidate_answer"].strip().lower() == task["reference_answer"].strip().lower() else 0.25
        print(json.dumps({
            "task_id": task["task_id"],
            "score": score,
            "passed": score >= payload["pass_threshold"],
        }))
        """,
    )

    evaluator = CommandAutoEvaluator(json.dumps([sys.executable, str(script)]))
    result = evaluator.evaluate(
        TaskSample(
            task_id="math-1",
            prompt="2+2",
            candidate_answer="4",
            reference_answer="4",
        )
    )

    assert result.task_id == "math-1"
    assert result.score == 1.0
    assert result.passed is True


def test_command_training_executor_can_delegate_and_save_result(tmp_path) -> None:
    script = tmp_path / "external_trainer.py"
    _write_script(
        script,
        """
        import json
        import sys

        payload = json.load(sys.stdin)
        request = payload["request"]
        metrics = request["metrics"]
        print(json.dumps({
            "strategy": request["strategy"],
            "status": "completed",
            "objective": f"external_{request['strategy']}",
            "input_samples": metrics["total"],
            "training_steps": metrics["total"] * 50,
            "epochs": 4,
            "curriculum_stage": request["curriculum_stage"],
            "policy_version": request["policy_version"],
            "artifact_path": f"external://{request['strategy']}",
        }))
        """,
    )

    executor = CommandTrainingExecutor(json.dumps([sys.executable, str(script)]))
    output = tmp_path / "training.json"
    result = executor.execute(
        TrainingExecutionRequest(
            strategy=TrainingStrategy.RL,
            metrics=DecisionMetrics(total=4, approve=3, review=1, block=0),
            curriculum_stage="reasoning",
            policy_version="v2",
        ),
        output_path=str(output),
    )

    assert result.strategy == TrainingStrategy.RL
    assert result.objective == "external_rl"
    assert result.training_steps == 200
    assert result.artifact_path == "external://rl"
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["artifact_path"] == "external://rl"


def test_cli_can_use_external_evaluator_and_training_backend(tmp_path) -> None:
    dataset = tmp_path / "tasks.json"
    summary = tmp_path / "summary.json"
    training_output = tmp_path / "training.json"
    evaluator_script = tmp_path / "external_evaluator.py"
    trainer_script = tmp_path / "external_trainer.py"

    dataset.write_text(
        json.dumps(
            [
                {
                    "task_id": "math-1",
                    "prompt": "2+2",
                    "candidate_answer": "4",
                    "reference_answer": "4",
                }
            ]
        ),
        encoding="utf-8",
    )
    _write_script(
        evaluator_script,
        """
        import json
        import sys

        payload = json.load(sys.stdin)
        task = payload["task"]
        score = 1.0 if task["candidate_answer"] == task["reference_answer"] else 0.0
        print(json.dumps({
            "task_id": task["task_id"],
            "score": score,
            "passed": score >= payload["pass_threshold"],
        }))
        """,
    )
    _write_script(
        trainer_script,
        """
        import json
        import sys

        payload = json.load(sys.stdin)
        request = payload["request"]
        metrics = request["metrics"]
        print(json.dumps({
            "strategy": request["strategy"],
            "status": "completed",
            "objective": "external_policy_optimization",
            "input_samples": metrics["total"],
            "training_steps": metrics["total"] * 100,
            "epochs": 5,
            "artifact_path": "external://trainer/demo",
        }))
        """,
    )

    run([
        "--start",
        "1",
        "--end",
        "1",
        "--task-dataset",
        str(dataset),
        "--reference-verifier",
        "--external-evaluator-cmd",
        json.dumps([sys.executable, str(evaluator_script)]),
        "--external-training-cmd",
        json.dumps([sys.executable, str(trainer_script)]),
        "--execute-training",
        "--training-strategy",
        "rl",
        "--training-output",
        str(training_output),
        "--output",
        str(summary),
    ])

    data = json.loads(summary.read_text(encoding="utf-8"))
    training_data = json.loads(training_output.read_text(encoding="utf-8"))
    assert data["inputs"]["evaluator"] == "CommandAutoEvaluator"
    assert data["inputs"]["training_executor"] == "CommandTrainingExecutor"
    assert data["inputs"]["external_evaluator_cmd"] == json.dumps([sys.executable, str(evaluator_script)])
    assert data["inputs"]["external_training_cmd"] == json.dumps([sys.executable, str(trainer_script)])
    assert data["dashboard"]["metrics"]["approve"] == 1
    assert data["training_execution"]["strategy"] == "rl"
    assert data["training_execution"]["objective"] == "external_policy_optimization"
    assert training_data["artifact_path"] == "external://trainer/demo"
