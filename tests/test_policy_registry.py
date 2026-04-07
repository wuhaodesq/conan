from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.reward_policy import RewardPolicy


def test_policy_registry_register_and_activate() -> None:
    engine = TrainingEngine()
    engine.pipeline.update_reward_policy(RewardPolicy(version="v2", approve_threshold=0.9))
    engine.register_policy(note="stricter threshold")

    assert "v2" in engine.policy_registry.versions

    engine.apply_policy_version("v2")
    assert engine.pipeline.config.reward_policy.version == "v2"


def test_policy_activation_event_logged() -> None:
    engine = TrainingEngine()
    engine.pipeline.update_reward_policy(RewardPolicy(version="v2"))
    engine.register_policy()
    engine.apply_policy_version("v2")

    events = [event.event_type for event in engine.tracker.events]
    assert "policy_registered" in events
    assert "policy_activated" in events
