import json

from hybrid_trainer.cli import run


def test_cli_can_export_events_and_state(tmp_path) -> None:
    summary = tmp_path / "summary.json"
    events = tmp_path / "events.jsonl"
    state = tmp_path / "state.json"

    run([
        "--start",
        "1",
        "--end",
        "5",
        "--output",
        str(summary),
        "--events-output",
        str(events),
        "--state-output",
        str(state),
    ])

    assert summary.exists()
    assert events.exists()
    assert state.exists()

    data = json.loads(summary.read_text())
    assert "dashboard" in data
    assert "reward_drift" in data
    assert events.read_text().strip() != ""
    assert json.loads(state.read_text())["strategy"] in {"sft", "rl", "dpo"}
