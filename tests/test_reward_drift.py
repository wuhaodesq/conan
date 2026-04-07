import json

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.reward_drift import compute_reward_drift


def test_compute_reward_drift_basic_ratio() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 5, DecisionNode.FAILURE_REVIEW)

    report = compute_reward_drift(engine.pipeline.history)
    assert report.total == 5
    assert report.review_or_block >= 1
    assert 0.0 <= report.drift_index <= 1.0


def test_cli_includes_reward_drift(tmp_path) -> None:
    from hybrid_trainer.cli import run

    output = run(["--start", "1", "--end", "3", "--output", str(tmp_path / "summary.json")])
    data = json.loads(output.read_text())

    assert "reward_drift" in data
    assert "drift_index" in data["reward_drift"]
