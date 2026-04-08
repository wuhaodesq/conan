import json

from hybrid_trainer.runtime_config import load_runtime_config


def test_load_runtime_config_reads_reward_policy_and_trigger_rules(tmp_path) -> None:
    config_path = tmp_path / "runtime_config.json"
    config_path.write_text(
        json.dumps(
            {
                "reward_policy": {
                    "version": "v2",
                    "approve_threshold": 0.9,
                    "review_band": 0.05,
                    "blocked_keywords": ["shortcut"],
                },
                "trigger_rules": {
                    "min_samples": 5,
                    "failure_review_block_ratio": 0.35,
                    "reward_calibration_review_ratio": 0.25,
                    "curriculum_shift_approve_ratio": 0.92,
                },
            }
        )
    )

    config = load_runtime_config(str(config_path))

    assert config.reward_policy.version == "v2"
    assert config.reward_policy.approve_threshold == 0.9
    assert config.reward_policy.blocked_keywords == ("shortcut",)
    assert config.trigger_rules.min_samples == 5
    assert config.trigger_rules.failure_review_block_ratio == 0.35
