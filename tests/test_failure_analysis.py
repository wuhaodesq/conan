from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.reward_policy import RewardPolicy
from hybrid_trainer.verifier import SimpleVerifier


def test_failure_taxonomy_counts_expected_categories() -> None:
    engine = TrainingEngine(verifier=SimpleVerifier(review_delta_threshold=0.0))
    engine.pipeline.update_reward_policy(RewardPolicy(blocked_keywords=("forbidden",)))

    # block by score
    engine.run_cycle(1, DecisionNode.FAILURE_REVIEW)
    # review from verifier override (approve -> review)
    engine.run_cycle(9, DecisionNode.REWARD_CALIBRATION)
    # block by policy keyword
    engine.pipeline.run_iteration(99, 0.95, DecisionNode.REWARD_CALIBRATION, candidate_answer="forbidden")

    taxonomy = engine.diagnose_failures()
    assert taxonomy.low_score_block >= 1
    assert taxonomy.verifier_override_review >= 1
    assert taxonomy.policy_block >= 1
    assert taxonomy.total_failures >= 3


def test_failure_diagnosis_event_logged() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    engine.diagnose_failures()

    assert any(event.event_type == "failure_diagnosed" for event in engine.tracker.events)
