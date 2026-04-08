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


def test_cli_run_can_load_runtime_config(tmp_path) -> None:
    output = tmp_path / "summary.json"
    config = tmp_path / "runtime_config.json"
    config.write_text(
        json.dumps(
            {
                "reward_policy": {
                    "version": "v2",
                    "approve_threshold": 0.95,
                    "review_band": 0.1,
                },
                "trigger_rules": {
                    "min_samples": 1,
                    "reward_calibration_review_ratio": 1.0,
                },
            }
        )
    )

    run([
        "--start",
        "9",
        "--end",
        "9",
        "--config",
        str(config),
        "--output",
        str(output),
    ])

    data = json.loads(output.read_text())
    assert data["config"]["reward_policy"]["version"] == "v2"
    assert data["dashboard"]["metrics"]["review"] == 1
