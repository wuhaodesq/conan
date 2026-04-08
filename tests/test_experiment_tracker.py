import json

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode


def test_tracker_collects_cycle_and_metrics_events(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycle(7, DecisionNode.FAILURE_REVIEW)
    engine.summarize_metrics()
    engine.execute_training(output_path=str(tmp_path / "training.json"))

    event_types = [event.event_type for event in engine.tracker.events]
    assert "cycle_completed" in event_types
    assert "metrics_summarized" in event_types
    assert "training_execution_completed" in event_types

    output = engine.tracker.export_jsonl(str(tmp_path / "events.jsonl"))
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["event_type"] == "cycle_completed"
