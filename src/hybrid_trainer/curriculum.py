from __future__ import annotations

from dataclasses import dataclass, field

from .metrics import DecisionMetrics


@dataclass(slots=True)
class CurriculumStage:
    name: str
    min_approve_ratio: float


@dataclass(slots=True)
class CurriculumAdvanceRecord:
    from_stage: str
    to_stage: str
    reason: str


@dataclass
class CurriculumManager:
    stages: list[CurriculumStage] = field(
        default_factory=lambda: [
            CurriculumStage("foundation", 0.70),
            CurriculumStage("intermediate", 0.82),
            CurriculumStage("advanced", 0.90),
        ]
    )
    current_index: int = 0
    history: list[CurriculumAdvanceRecord] = field(default_factory=list)

    @property
    def current_stage(self) -> CurriculumStage:
        return self.stages[self.current_index]

    def maybe_advance(self, metrics: DecisionMetrics) -> CurriculumAdvanceRecord | None:
        if metrics.total == 0 or self.current_index >= len(self.stages) - 1:
            return None

        approve_ratio = metrics.approve / metrics.total
        next_stage = self.stages[self.current_index + 1]
        if approve_ratio >= next_stage.min_approve_ratio:
            record = CurriculumAdvanceRecord(
                from_stage=self.current_stage.name,
                to_stage=next_stage.name,
                reason=f"approve_ratio={approve_ratio:.2f} 达到 {next_stage.min_approve_ratio:.2f}",
            )
            self.history.append(record)
            self.current_index += 1
            return record

        return None
