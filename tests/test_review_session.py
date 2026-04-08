import json

from hybrid_trainer.cli import run
from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.human_review import HumanReviewDecision
from hybrid_trainer.pipeline import Decision, DecisionNode
from hybrid_trainer.review_router import route_review_items
from hybrid_trainer.review_session import (
    ReviewSession,
    export_review_session_decisions,
    load_review_decision_payload,
    load_review_session,
    save_review_session,
)


def test_review_session_can_sync_multiple_reviewers_and_detect_conflicts(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
    batch = route_review_items(engine.review_queue.pending, budget=2)

    session = ReviewSession.create(console=console, batch=batch)
    first_iteration = batch.items[0].iteration
    session.sync_reviewer_submission(
        reviewer="alice",
        role="reviewer",
        decisions=[
            HumanReviewDecision(
                iteration=first_iteration,
                final_decision=Decision.APPROVE,
                reviewer="alice",
                note="approved after review",
            )
        ],
    )

    session.sync_reviewer_submission(
        reviewer="bob",
        role="reviewer",
        decisions=[
            HumanReviewDecision(
                iteration=first_iteration,
                final_decision=Decision.BLOCK,
                reviewer="bob",
                note="prefer conservative block",
            )
        ],
    )

    summary = session.summary()
    assert summary["total_reviewers"] == 2
    assert summary["submitted_decisions"] == 2
    assert summary["conflict_iterations"] == 1

    output = save_review_session(session, str(tmp_path / "session.json"))
    loaded = load_review_session(str(output))
    exported = tmp_path / "decisions.json"
    export_review_session_decisions(loaded, str(exported))
    exported_payload = json.loads(exported.read_text(encoding="utf-8"))
    assert len(exported_payload["decisions"]) == 2


def test_load_review_decision_payload_reads_top_level_role(tmp_path) -> None:
    payload = tmp_path / "review_decisions.json"
    payload.write_text(
        json.dumps(
            {
                "reviewer": "alice",
                "role": "triager",
                "decisions": [
                    {
                        "iteration": 7,
                        "final_decision": "approve",
                        "reviewer": "alice",
                        "note": "looks good",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    decisions, role = load_review_decision_payload(str(payload))

    assert role == "triager"
    assert decisions[0].reviewer == "alice"


def test_cli_can_create_and_update_review_session(tmp_path) -> None:
    session = tmp_path / "review_session.json"
    updated_summary = tmp_path / "summary.json"
    decisions = tmp_path / "review_decisions.json"
    exported = tmp_path / "session_decisions.json"

    run([
        "--start",
        "1",
        "--end",
        "3",
        "--node",
        "failure_review",
        "--review-budget",
        "2",
        "--review-session-output",
        str(session),
        "--review-session-id",
        "session-alpha",
        "--output",
        str(tmp_path / "create_summary.json"),
    ])

    session_payload = json.loads(session.read_text(encoding="utf-8"))
    first_iteration = session_payload["review_batch"]["items"][0]["iteration"]
    decisions.write_text(
        json.dumps(
            {
                "reviewer": "alice",
                "role": "reviewer",
                "decisions": [
                    {
                        "iteration": first_iteration,
                        "final_decision": "approve",
                        "reviewer": "alice",
                        "note": "approved from browser",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    run([
        "--start",
        "1",
        "--end",
        "3",
        "--node",
        "failure_review",
        "--review-session-input",
        str(session),
        "--review-decisions-input",
        str(decisions),
        "--review-role",
        "reviewer",
        "--review-session-export-decisions",
        str(exported),
        "--output",
        str(updated_summary),
    ])

    updated_session = json.loads(session.read_text(encoding="utf-8"))
    updated_payload = json.loads(updated_summary.read_text(encoding="utf-8"))
    exported_payload = json.loads(exported.read_text(encoding="utf-8"))

    assert updated_session["summary"]["session_id"] == "session-alpha"
    assert updated_session["summary"]["submitted_decisions"] == 1
    assert updated_payload["review_session"]["submitted_decisions"] == 1
    assert exported_payload["decisions"][0]["reviewer"] == "alice"
