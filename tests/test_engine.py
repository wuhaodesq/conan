from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import Decision, DecisionNode


def test_cycle_approve() -> None:
    engine = TrainingEngine()
    cycle = engine.run_cycle(9, DecisionNode.REWARD_CALIBRATION)
    assert cycle.score == 0.9
    assert cycle.decision_report.decision == Decision.APPROVE


def test_cycle_review() -> None:
    engine = TrainingEngine()
    cycle = engine.run_cycle(7, DecisionNode.FAILURE_REVIEW)
    assert cycle.score == 0.7
    assert cycle.decision_report.decision == Decision.REVIEW


def test_cycle_block() -> None:
    engine = TrainingEngine()
    cycle = engine.run_cycle(2, DecisionNode.CURRICULUM_SHIFT)
    assert cycle.score == 0.2
    assert cycle.decision_report.decision == Decision.BLOCK
