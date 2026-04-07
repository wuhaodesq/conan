from __future__ import annotations

from dataclasses import dataclass, field

from .reward_policy import RewardPolicy


@dataclass(slots=True)
class PolicyVersionRecord:
    version: str
    note: str
    policy: RewardPolicy


@dataclass
class PolicyRegistry:
    versions: dict[str, PolicyVersionRecord] = field(default_factory=dict)
    active_version: str | None = None

    def register(self, policy: RewardPolicy, note: str = "") -> PolicyVersionRecord:
        record = PolicyVersionRecord(version=policy.version, note=note, policy=policy)
        self.versions[policy.version] = record
        if self.active_version is None:
            self.active_version = policy.version
        return record

    def activate(self, version: str) -> RewardPolicy:
        if version not in self.versions:
            raise KeyError(f"Unknown policy version: {version}")
        self.active_version = version
        return self.versions[version].policy

    def get_active_policy(self) -> RewardPolicy | None:
        if self.active_version is None:
            return None
        return self.versions[self.active_version].policy
