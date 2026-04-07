from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode


def test_generate_dashboard_contains_metrics_failures_and_recommendations() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 5, DecisionNode.FAILURE_REVIEW)

    dashboard = engine.generate_dashboard()
    data = dashboard.to_dict()

    assert "metrics" in data
    assert "failures" in data
    assert "recommended_nodes" in data
    assert data["metrics"]["total"] == 5


def test_dashboard_event_logged() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    engine.generate_dashboard()

    assert any(event.event_type == "dashboard_generated" for event in engine.tracker.events)
