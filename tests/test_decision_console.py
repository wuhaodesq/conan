import json

from hybrid_trainer.pipeline import Decision
from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.decision_console import save_decision_console


def test_generate_decision_console_contains_review_queue_and_policy(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 5, DecisionNode.FAILURE_REVIEW)
    engine.review_queue.resolve(1, Decision.APPROVE, "alice", "saved")

    console = engine.generate_decision_console(review_budget=2, active_learning_limit=3, recent_event_limit=5)
    data = console.to_dict()

    assert "dashboard" in data
    assert "review_queue" in data
    assert data["review_queue"]["pending_count"] == 4
    assert len(data["review_queue"]["prioritized_items"]) == 2
    assert len(data["review_queue"]["recent_resolutions"]) == 1
    assert "active_learning" in data
    assert len(data["active_learning"]["candidates"]) == 3
    assert data["policy"]["active_version"] == "v1"
    assert data["strategy"]["current"] == "sft"

    output = save_decision_console(console, str(tmp_path / "console.json"))
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["review_queue"]["budget"] == 2


def test_decision_console_event_logged() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    engine.generate_decision_console()

    assert any(event.event_type == "decision_console_generated" for event in engine.tracker.events)
