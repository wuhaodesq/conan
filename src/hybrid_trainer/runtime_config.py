from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .reward_policy import RewardPolicy
from .triggers import TriggerRuleConfig


@dataclass(slots=True)
class RuntimeConfig:
    reward_policy: RewardPolicy = field(default_factory=RewardPolicy)
    trigger_rules: TriggerRuleConfig = field(default_factory=TriggerRuleConfig)

    def to_dict(self) -> dict:
        return {
            "reward_policy": self.reward_policy.to_dict(),
            "trigger_rules": self.trigger_rules.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RuntimeConfig":
        return cls(
            reward_policy=RewardPolicy.from_dict(payload.get("reward_policy") or {}),
            trigger_rules=TriggerRuleConfig.from_dict(payload.get("trigger_rules") or {}),
        )


def load_runtime_config(path: str) -> RuntimeConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return RuntimeConfig.from_dict(payload)
