from hybrid_trainer.pipeline import Decision, DecisionNode, TrainingPipeline


def test_approve_path() -> None:
    pipeline = TrainingPipeline()
    report = pipeline.run_iteration(1, 0.9, DecisionNode.REWARD_CALIBRATION)
    assert report.decision == Decision.APPROVE


def test_review_path() -> None:
    pipeline = TrainingPipeline()
    report = pipeline.run_iteration(2, 0.7, DecisionNode.FAILURE_REVIEW)
    assert report.decision == Decision.REVIEW


def test_block_path() -> None:
    pipeline = TrainingPipeline()
    report = pipeline.run_iteration(3, 0.3, DecisionNode.CURRICULUM_SHIFT)
    assert report.decision == Decision.BLOCK
