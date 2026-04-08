import json

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.strategy import TrainingStrategy


def test_execute_training_uses_current_strategy_and_logs_events(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(7, 13, DecisionNode.REWARD_CALIBRATION)
    engine.maybe_switch_strategy()

    result = engine.execute_training(output_path=str(tmp_path / "training.json"))

    assert result.strategy == TrainingStrategy.RL
    assert result.status == "completed"
    assert result.training_steps > 0
    assert any(event.event_type == "training_execution_started" for event in engine.tracker.events)
    assert any(event.event_type == "training_execution_completed" for event in engine.tracker.events)
    saved = json.loads((tmp_path / "training.json").read_text(encoding="utf-8"))
    assert saved["strategy"] == "rl"


def test_execute_training_allows_explicit_strategy_override() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 5, DecisionNode.FAILURE_REVIEW)

    result = engine.execute_training(strategy=TrainingStrategy.DPO)

    assert result.strategy == TrainingStrategy.DPO
    assert result.objective == "preference_optimization"
