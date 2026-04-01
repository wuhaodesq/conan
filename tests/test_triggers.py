from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode


def test_recommend_failure_review_when_block_ratio_high() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 4, DecisionNode.FAILURE_REVIEW)  # mostly blocks

    recommendations = engine.recommend_nodes()
    nodes = {item.node for item in recommendations}
    assert DecisionNode.FAILURE_REVIEW in nodes


def test_recommend_curriculum_shift_when_approve_ratio_high() -> None:
    engine = TrainingEngine()
    engine.run_cycles(9, 20, DecisionNode.REWARD_CALIBRATION)

    recommendations = engine.recommend_nodes()
    nodes = {item.node for item in recommendations}
    assert DecisionNode.CURRICULUM_SHIFT in nodes
