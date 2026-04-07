import json

from hybrid_trainer.cli import run


def test_cli_run_writes_summary_file(tmp_path) -> None:
    output = tmp_path / "summary.json"
    result = run([
        "--start",
        "7",
        "--end",
        "9",
        "--node",
        "reward_calibration",
        "--output",
        str(output),
    ])

    assert result == output
    data = json.loads(output.read_text())
    assert data["range"] == {"start": 7, "end": 9}
    assert data["dashboard"]["metrics"]["total"] == 3
    assert "strategy" in data
    assert "curriculum" in data
