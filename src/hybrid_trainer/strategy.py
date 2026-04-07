from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .metrics import DecisionMetrics


class TrainingStrategy(str, Enum):
    SFT = "sft"
    RL = "rl"
    DPO = "dpo"


@dataclass(slots=True)
class StrategySwitchRecord:
    from_strategy: TrainingStrategy
    to_strategy: TrainingStrategy
    reason: str


@dataclass
class StrategyManager:
    current: TrainingStrategy = TrainingStrategy.SFT
    history: list[StrategySwitchRecord] = field(default_factory=list)

    def recommend(self, metrics: DecisionMetrics) -> tuple[TrainingStrategy, str]:
        if metrics.total == 0:
            return self.current, "暂无训练历史，保持当前策略"

        approve_ratio = metrics.approve / metrics.total
        block_ratio = metrics.block / metrics.total

        if block_ratio >= 0.4:
            return TrainingStrategy.SFT, "Block 偏高，回到 SFT 修复基础能力"

        if approve_ratio >= 0.9 and metrics.review == 0:
            return TrainingStrategy.DPO, "高质量稳定输出，可引入偏好优化"

        if approve_ratio >= 0.85 and metrics.review <= 1:
            return TrainingStrategy.RL, "表现稳定，建议切换到 RL 提升探索能力"

        return self.current, "维持当前策略继续收集信号"

    def maybe_switch(self, metrics: DecisionMetrics) -> StrategySwitchRecord | None:
        target, reason = self.recommend(metrics)
        if target == self.current:
            return None

        record = StrategySwitchRecord(
            from_strategy=self.current,
            to_strategy=target,
            reason=reason,
        )
        self.history.append(record)
        self.current = target
        return record
