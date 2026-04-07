from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode


def test_collect_active_learning_candidates_prefers_near_threshold() -> None:
    engine = TrainingEngine()
    engine.run_cycles(5, 10, DecisionNode.REWARD_CALIBRATION)

    candidates = engine.collect_active_learning_candidates(limit=3)
    assert len(candidates) == 3

    # Threshold=0.8 so 8 is closest; 7 and 9 are tied near-threshold samples
    assert candidates[0].iteration == 8
    assert {item.iteration for item in candidates[1:]} == {7, 9}


def test_active_learning_event_logged() -> None:
    engine = TrainingEngine()
    engine.run_cycles(6, 9, DecisionNode.FAILURE_REVIEW)
    engine.collect_active_learning_candidates(limit=2)

    assert any(event.event_type == "active_learning_selected" for event in engine.tracker.events)
