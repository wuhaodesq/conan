from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode


def test_curriculum_advances_when_approve_ratio_high() -> None:
    engine = TrainingEngine()
    assert engine.curriculum_manager.current_stage.name == "foundation"

    engine.run_cycles(8, 12, DecisionNode.CURRICULUM_SHIFT)
    record = engine.maybe_advance_curriculum()

    assert record is not None
    assert record.from_stage == "foundation"
    assert record.to_stage == "intermediate"
    assert engine.curriculum_manager.current_stage.name == "intermediate"


def test_curriculum_event_is_tracked() -> None:
    engine = TrainingEngine()
    engine.run_cycles(9, 15, DecisionNode.CURRICULUM_SHIFT)
    engine.maybe_advance_curriculum()

    event_types = [event.event_type for event in engine.tracker.events]
    assert "curriculum_advanced" in event_types
