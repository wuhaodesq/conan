import json
import sys
import textwrap

from hybrid_trainer.cli import run
from hybrid_trainer.generation import CommandTaskGenerator
from hybrid_trainer.model_service import ModelServiceRegistry


def _write_script(path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def test_command_task_generator_can_delegate_to_external_script(tmp_path) -> None:
    script = tmp_path / "generator.py"
    _write_script(
        script,
        """
        import json
        import sys

        payload = json.load(sys.stdin)
        iteration = payload["iteration"]
        print(json.dumps({
            "task": {
                "task_id": f"svc-{iteration}",
                "prompt": f"Solve {iteration}",
                "candidate_answer": str(iteration * 2),
                "reference_answer": str(iteration * 2),
            }
        }))
        """,
    )

    generator = CommandTaskGenerator(json.dumps([sys.executable, str(script)]))
    sample = generator.generate(3)

    assert sample.task_id == "svc-3"
    assert sample.reference_answer == "6"


def test_model_service_registry_can_load_named_services(tmp_path) -> None:
    services = tmp_path / "services.json"
    services.write_text(
        json.dumps(
            {
                "services": [
                    {
                        "name": "generator.mock",
                        "role": "generator",
                        "command": ["python", "gen.py"],
                        "timeout_seconds": 15,
                    },
                    {
                        "name": "trainer.mock",
                        "role": "training",
                        "command": "python train.py",
                        "timeout_seconds": 45,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    registry = ModelServiceRegistry.from_file(str(services))

    assert registry.resolve("generator.mock", role="generator").timeout_seconds == 15
    assert registry.resolve("trainer.mock", role="training").command == "python train.py"


def test_cli_can_use_model_services_and_export_job_orchestration(tmp_path) -> None:
    summary = tmp_path / "summary.json"
    training = tmp_path / "training.json"
    jobs = tmp_path / "jobs.json"
    services = tmp_path / "services.json"
    generator_script = tmp_path / "generator.py"
    evaluator_script = tmp_path / "evaluator.py"
    trainer_script = tmp_path / "trainer.py"

    _write_script(
        generator_script,
        """
        import json
        import sys

        payload = json.load(sys.stdin)
        iteration = payload["iteration"]
        print(json.dumps({
            "task": {
                "task_id": f"queue-{iteration}",
                "prompt": f"Task {iteration}",
                "candidate_answer": "approved",
                "reference_answer": "approved",
            }
        }))
        """,
    )
    _write_script(
        evaluator_script,
        """
        import json
        import sys

        payload = json.load(sys.stdin)
        print(json.dumps({
            "task_id": payload["task"]["task_id"],
            "score": 1.0,
            "passed": True,
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
        print(json.dumps({
            "strategy": request["strategy"],
            "status": "completed",
            "objective": "queued_training",
            "input_samples": request["metrics"]["total"],
            "training_steps": request["metrics"]["total"] * 60,
            "epochs": 2,
            "curriculum_stage": request["curriculum_stage"],
            "policy_version": request["policy_version"],
            "artifact_path": "queue://training/result",
        }))
        """,
    )
    services.write_text(
        json.dumps(
            {
                "services": [
                    {
                        "name": "generator.queue",
                        "role": "generator",
                        "command": [sys.executable, str(generator_script)],
                        "timeout_seconds": 30,
                    },
                    {
                        "name": "evaluator.queue",
                        "role": "evaluator",
                        "command": [sys.executable, str(evaluator_script)],
                        "timeout_seconds": 30,
                    },
                    {
                        "name": "training.queue",
                        "role": "training",
                        "command": [sys.executable, str(trainer_script)],
                        "timeout_seconds": 60,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    run([
        "--start",
        "1",
        "--end",
        "1",
        "--reference-verifier",
        "--model-service-config",
        str(services),
        "--generator-service",
        "generator.queue",
        "--evaluator-service",
        "evaluator.queue",
        "--training-service",
        "training.queue",
        "--job-orchestration-output",
        str(jobs),
        "--execute-training",
        "--training-output",
        str(training),
        "--output",
        str(summary),
    ])

    summary_data = json.loads(summary.read_text(encoding="utf-8"))
    training_data = json.loads(training.read_text(encoding="utf-8"))
    jobs_data = json.loads(jobs.read_text(encoding="utf-8"))

    assert summary_data["inputs"]["generator"] == "CommandTaskGenerator"
    assert summary_data["inputs"]["evaluator"] == "CommandAutoEvaluator"
    assert summary_data["inputs"]["training_executor"] == "CommandTrainingExecutor"
    assert summary_data["inputs"]["generator_service"] == "generator.queue"
    assert summary_data["inputs"]["evaluator_service"] == "evaluator.queue"
    assert summary_data["inputs"]["training_service"] == "training.queue"
    assert summary_data["job_orchestration"]["completed_jobs"] == 3
    assert jobs_data["summary"]["services"] == ["evaluator.queue", "generator.queue", "training.queue"]
    assert jobs_data["jobs"][0]["kind"] == "task_generation"
    assert jobs_data["jobs"][1]["dependencies"] == [jobs_data["jobs"][0]["job_id"]]
    assert jobs_data["jobs"][2]["dependencies"] == [jobs_data["jobs"][1]["job_id"]]
    assert training_data["objective"] == "queued_training"
