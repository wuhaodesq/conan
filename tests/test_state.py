from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.state import load_snapshot, save_snapshot
from hybrid_trainer.strategy import TrainingStrategy


def test_state_snapshot_save_and_load(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(7, 10, DecisionNode.REWARD_CALIBRATION)
    engine.maybe_switch_strategy()

    snapshot = engine.snapshot_state()
    output = save_snapshot(snapshot, str(tmp_path / "state.json"))
    restored = load_snapshot(str(output))

    assert restored.strategy == engine.strategy_manager.current
    assert restored.history_count == len(engine.pipeline.history)


def test_restore_state_sets_strategy_and_curriculum() -> None:
    engine = TrainingEngine()
    engine.strategy_manager.current = TrainingStrategy.DPO
    engine.curriculum_manager.current_index = 2

    snapshot = engine.snapshot_state()

    other = TrainingEngine()
    other.restore_state(snapshot)

    assert other.strategy_manager.current == TrainingStrategy.DPO
    assert other.curriculum_manager.current_stage.name == "advanced"
