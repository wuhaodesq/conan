import json

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.human_review import HumanReviewDecision
from hybrid_trainer.pipeline import Decision, DecisionNode
from hybrid_trainer.review_consensus import build_review_consensus, save_review_consensus


def test_build_review_consensus_detects_majority_consensus() -> None:
    records = build_review_consensus(
        [
            HumanReviewDecision(iteration=1, final_decision=Decision.APPROVE, reviewer="alice"),
            HumanReviewDecision(iteration=1, final_decision=Decision.APPROVE, reviewer="bob"),
        ],
        min_reviewers=2,
    )

    assert records[0].status == "consensus"
    assert records[0].final_decision == Decision.APPROVE


def test_build_review_consensus_arbitrates_tie_conservatively() -> None:
    records = build_review_consensus(
        [
            HumanReviewDecision(iteration=1, final_decision=Decision.APPROVE, reviewer="alice"),
            HumanReviewDecision(iteration=1, final_decision=Decision.BLOCK, reviewer="bob"),
        ],
        min_reviewers=2,
    )

    assert records[0].status == "arbitrated"
    assert records[0].final_decision == Decision.BLOCK


def test_engine_apply_review_consensus_resolves_pending_items(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 2, DecisionNode.FAILURE_REVIEW)

    records = engine.apply_review_consensus(
        [
            HumanReviewDecision(iteration=1, final_decision=Decision.REVIEW, reviewer="alice"),
            HumanReviewDecision(iteration=1, final_decision=Decision.REVIEW, reviewer="bob"),
        ],
        min_reviewers=2,
    )

    assert records[0].status == "consensus"
    assert len(engine.review_queue.resolved) == 1
    assert any(event.event_type == "review_consensus_applied" for event in engine.tracker.events)

    output = save_review_consensus(records, str(tmp_path / "consensus.json"))
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["records"][0]["status"] == "consensus"
