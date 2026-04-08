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

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "approve_threshold": self.approve_threshold,
            "review_band": self.review_band,
            "blocked_keywords": list(self.blocked_keywords),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RewardPolicy":
        return cls(
            version=str(payload.get("version", "v1")),
            approve_threshold=float(payload.get("approve_threshold", 0.8)),
            review_band=float(payload.get("review_band", 0.15)),
            blocked_keywords=tuple(payload.get("blocked_keywords") or ()),
        )
