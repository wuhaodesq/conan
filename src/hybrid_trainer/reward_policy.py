from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RewardPolicy:
    version: str = "v1"
    approve_threshold: float = 0.8
    review_band: float = 0.15
    blocked_keywords: tuple[str, ...] = field(default_factory=tuple)

    def should_block_answer(self, answer: str) -> bool:
        lowered = answer.lower()
        return any(keyword.lower() in lowered for keyword in self.blocked_keywords)
