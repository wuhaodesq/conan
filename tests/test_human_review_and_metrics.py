from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.human_review import HumanReviewDecision
from hybrid_trainer.metrics import summarize_decisions
from hybrid_trainer.pipeline import Decision, DecisionNode


def test_review_queue_receives_non_approved_items() -> None:
    engine = TrainingEngine()
    engine.run_cycle(9, DecisionNode.REWARD_CALIBRATION)  # approve
    engine.run_cycle(7, DecisionNode.FAILURE_REVIEW)      # review
    engine.run_cycle(2, DecisionNode.CURRICULUM_SHIFT)    # block

    assert len(engine.review_queue.pending) == 2
    assert {item.auto_decision for item in engine.review_queue.pending} == {Decision.REVIEW, Decision.BLOCK}


def test_review_resolution_and_metrics_summary() -> None:
    engine = TrainingEngine()
    engine.run_cycles(6, 9, DecisionNode.FAILURE_REVIEW)

    # 6 -> block; 7 -> review; 8,9 -> approve
    metrics = summarize_decisions(engine.pipeline.history)
    assert metrics.total == 4
    assert metrics.approve == 2
    assert metrics.review == 1
    assert metrics.block == 1

    resolved = engine.review_queue.resolve(
        iteration=6,
        final_decision=Decision.APPROVE,
        reviewer="alice",
        note="Accepted after manual inspection",
    )
    assert resolved.reviewer == "alice"
    assert resolved.final_decision == Decision.APPROVE
    assert all(item.iteration != 6 for item in engine.review_queue.pending)


def test_apply_review_decisions_updates_resolved_queue_and_tracks_event() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)

    resolved = engine.apply_review_decisions([
        HumanReviewDecision(iteration=1, final_decision=Decision.APPROVE, reviewer="alice", note="rescued"),
        HumanReviewDecision(iteration=2, final_decision=Decision.BLOCK, reviewer="bob", note="confirmed"),
    ])

    assert len(resolved) == 2
    assert len(engine.review_queue.pending) == 1
    assert len(engine.review_queue.resolved) == 2
    assert any(event.event_type == "review_decisions_applied" for event in engine.tracker.events)
