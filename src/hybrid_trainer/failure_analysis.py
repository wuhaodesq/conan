from __future__ import annotations

from dataclasses import dataclass

from .pipeline import Decision, IterationReport


@dataclass(slots=True)
class FailureTaxonomy:
    low_score_block: int
    policy_block: int
    verifier_override_review: int
    generic_review: int

    @property
    def total_failures(self) -> int:
        return self.low_score_block + self.policy_block + self.verifier_override_review + self.generic_review


def analyze_failures(history: list[IterationReport]) -> FailureTaxonomy:
    low_score_block = 0
    policy_block = 0
    verifier_override_review = 0
    generic_review = 0

    for item in history:
        if item.decision == Decision.BLOCK:
            if "黑名单词" in item.reason:
                policy_block += 1
            else:
                low_score_block += 1
        elif item.decision == Decision.REVIEW:
            if "Verifier 偏差" in item.reason:
                verifier_override_review += 1
            else:
                generic_review += 1

    return FailureTaxonomy(
        low_score_block=low_score_block,
        policy_block=policy_block,
        verifier_override_review=verifier_override_review,
        generic_review=generic_review,
    )
