from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import Decision, DecisionNode
from hybrid_trainer.verifier import SimpleVerifier


def test_verifier_can_override_approve_to_review() -> None:
    engine = TrainingEngine(verifier=SimpleVerifier(review_delta_threshold=0.0))
    cycle = engine.run_cycle(9, DecisionNode.REWARD_CALIBRATION)

    assert cycle.decision_report.decision == Decision.REVIEW
    assert any(event.event_type == "verifier_override" for event in engine.tracker.events)


def test_verifier_no_override_when_threshold_high() -> None:
    engine = TrainingEngine(verifier=SimpleVerifier(review_delta_threshold=1.0))
    cycle = engine.run_cycle(9, DecisionNode.REWARD_CALIBRATION)

    assert cycle.decision_report.decision == Decision.APPROVE
