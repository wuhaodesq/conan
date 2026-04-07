import json

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode


def test_analyze_cost_returns_positive_values() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 5, DecisionNode.FAILURE_REVIEW)

    cost = engine.analyze_cost()
    assert cost.total_iterations == 5
    assert cost.auto_evaluation_cost > 0
    assert cost.human_review_cost >= 0
    assert cost.total_cost == cost.auto_evaluation_cost + cost.human_review_cost


def test_cli_includes_cost_section(tmp_path) -> None:
    from hybrid_trainer.cli import run

    output = run(["--start", "1", "--end", "3", "--output", str(tmp_path / "summary.json")])
    data = json.loads(output.read_text())

    assert "cost" in data
    assert "total_cost" in data["cost"]
