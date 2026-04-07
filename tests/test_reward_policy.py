from hybrid_trainer.pipeline import Decision, DecisionNode, TrainingPipeline
from hybrid_trainer.reward_policy import RewardPolicy


def test_blocked_keyword_forces_block() -> None:
    pipeline = TrainingPipeline()
    pipeline.update_reward_policy(
        RewardPolicy(version="v2", approve_threshold=0.8, review_band=0.1, blocked_keywords=("forbidden",))
    )

    report = pipeline.run_iteration(
        iteration=1,
        auto_score=0.95,
        node=DecisionNode.REWARD_CALIBRATION,
        candidate_answer="This answer has forbidden trick",
    )
    assert report.decision == Decision.BLOCK
    assert "v2" in report.reason


def test_policy_threshold_changes_review_behavior() -> None:
    pipeline = TrainingPipeline()
    pipeline.update_reward_policy(
        RewardPolicy(version="v3", approve_threshold=0.9, review_band=0.2)
    )

    report = pipeline.run_iteration(
        iteration=2,
        auto_score=0.75,
        node=DecisionNode.FAILURE_REVIEW,
    )
    assert report.decision == Decision.REVIEW
    assert "v3" in report.reason
