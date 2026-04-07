from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.search import PathCandidate, select_best_path


def test_select_best_path_picks_highest_score() -> None:
    best = select_best_path([
        PathCandidate(path_id=0, score=0.4, answer="a"),
        PathCandidate(path_id=1, score=0.9, answer="b"),
        PathCandidate(path_id=2, score=0.7, answer="c"),
    ])
    assert best.path_id == 1


def test_run_multi_path_cycle_tracks_selected_path() -> None:
    engine = TrainingEngine()
    cycle = engine.run_multi_path_cycle(9, DecisionNode.REWARD_CALIBRATION, num_paths=3)

    assert cycle.score >= 0.0
    assert any(event.event_type == "multi_path_selected" for event in engine.tracker.events)
