import json

from hybrid_trainer.cli import run


def test_cli_can_export_events_and_state(tmp_path) -> None:
    summary = tmp_path / "summary.json"
    console = tmp_path / "console.json"
    review_batch = tmp_path / "review_batch.json"
    review_decisions = tmp_path / "review_decisions.json"
    events = tmp_path / "events.jsonl"
    state = tmp_path / "state.json"
    review_decisions.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "iteration": 1,
                        "final_decision": "approve",
                        "reviewer": "alice",
                        "note": "approved manually",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    run([
        "--start",
        "1",
        "--end",
        "5",
        "--output",
        str(summary),
        "--console-output",
        str(console),
        "--review-batch-output",
        str(review_batch),
        "--review-decisions-input",
        str(review_decisions),
        "--events-output",
        str(events),
        "--state-output",
        str(state),
    ])

    assert summary.exists()
    assert console.exists()
    assert review_batch.exists()
    assert events.exists()
    assert state.exists()

    data = json.loads(summary.read_text(encoding="utf-8"))
    console_data = json.loads(console.read_text(encoding="utf-8"))
    assert "dashboard" in data
    assert data["human_review"]["resolved"] == 1
    assert "reward_drift" in data
    assert "review_queue" in console_data
    assert console_data["review_queue"]["resolved_count"] == 1
    assert "policy" in console_data
    assert events.read_text(encoding="utf-8").strip() != ""
    assert json.loads(state.read_text(encoding="utf-8"))["strategy"] in {"sft", "rl", "dpo"}
