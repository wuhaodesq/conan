from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.metrics import DecisionMetrics
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.triggers import TriggerRuleConfig, recommend_major_nodes


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


def test_custom_trigger_rules_can_lower_review_threshold() -> None:
    metrics = DecisionMetrics(total=10, approve=6, review=2, block=2)

    recommendations = recommend_major_nodes(
        metrics,
        TriggerRuleConfig(reward_calibration_review_ratio=0.2),
    )

    nodes = {item.node for item in recommendations}
    assert DecisionNode.REWARD_CALIBRATION in nodes


def test_custom_trigger_rules_can_require_minimum_samples() -> None:
    metrics = DecisionMetrics(total=2, approve=2, review=0, block=0)

    recommendations = recommend_major_nodes(
        metrics,
        TriggerRuleConfig(min_samples=3),
    )

    assert recommendations == []
