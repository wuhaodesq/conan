import json

from hybrid_trainer.cli import run
from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.generation import DatasetTaskGenerator, TaskSample
from hybrid_trainer.pipeline import Decision, DecisionNode
from hybrid_trainer.verifier import ReferenceAnswerVerifier


def test_dataset_task_generator_cycles_loaded_samples(tmp_path) -> None:
    dataset = tmp_path / "tasks.json"
    dataset.write_text(
        json.dumps(
            [
                {"task_id": "math-1", "prompt": "2+2", "candidate_answer": "4", "reference_answer": "4"},
                {"task_id": "logic-1", "prompt": "yes/no", "candidate_answer": "yes", "reference_answer": "yes"},
            ]
        ),
        encoding="utf-8",
    )

    generator = DatasetTaskGenerator.from_file(str(dataset))
    first = generator.generate(1)
    third = generator.generate(3)

    assert first.task_id == "math-1"
    assert third.task_id == "math-1"


def test_reference_dataset_can_drive_engine_to_approve() -> None:
    generator = DatasetTaskGenerator(
        [
            TaskSample(
                task_id="math-1",
                prompt="2+2",
                candidate_answer="4",
                reference_answer="4",
            )
        ]
    )
    engine = TrainingEngine(
        generator=generator,
        verifier=ReferenceAnswerVerifier(review_delta_threshold=0.1),
    )

    cycle = engine.run_cycle(1, DecisionNode.REWARD_CALIBRATION)

    assert cycle.score == 1.0
    assert cycle.decision_report.decision == Decision.APPROVE


def test_cli_can_use_task_dataset_and_reference_verifier(tmp_path) -> None:
    dataset = tmp_path / "tasks.json"
    output = tmp_path / "summary.json"
    dataset.write_text(
        json.dumps(
            [
                {"task_id": "math-1", "prompt": "2+2", "candidate_answer": "4", "reference_answer": "4"},
            ]
        ),
        encoding="utf-8",
    )

    run([
        "--start",
        "1",
        "--end",
        "1",
        "--task-dataset",
        str(dataset),
        "--reference-verifier",
        "--output",
        str(output),
    ])

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["inputs"]["task_dataset"] == str(dataset)
    assert data["inputs"]["verifier"] == "ReferenceAnswerVerifier"
    assert data["dashboard"]["metrics"]["approve"] == 1
