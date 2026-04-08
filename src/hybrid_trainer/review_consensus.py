from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from pathlib import Path

from .human_review import HumanReviewDecision
from .pipeline import Decision


@dataclass(slots=True)
class ReviewConsensusRecord:
    iteration: int
    reviewer_count: int
    reviewers: tuple[str, ...]
    vote_counts: dict[str, int]
    agreement_ratio: float
    status: str
    final_decision: Decision | None
    rationale: str

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "reviewer_count": self.reviewer_count,
            "reviewers": list(self.reviewers),
            "vote_counts": dict(self.vote_counts),
            "agreement_ratio": self.agreement_ratio,
            "status": self.status,
            "final_decision": self.final_decision.value if self.final_decision is not None else None,
            "rationale": self.rationale,
        }


def build_review_consensus(
    decisions: list[HumanReviewDecision],
    min_reviewers: int = 2,
) -> list[ReviewConsensusRecord]:
    grouped: dict[int, list[HumanReviewDecision]] = defaultdict(list)
    for item in decisions:
        grouped[item.iteration].append(item)

    records: list[ReviewConsensusRecord] = []
    for iteration in sorted(grouped):
        items = grouped[iteration]
        counts = Counter(item.final_decision for item in items)
        reviewer_count = len(items)
        reviewers = tuple(item.reviewer for item in items)
        top_votes = counts.most_common()

        if reviewer_count < min_reviewers:
            records.append(
                ReviewConsensusRecord(
                    iteration=iteration,
                    reviewer_count=reviewer_count,
                    reviewers=reviewers,
                    vote_counts={decision.value: count for decision, count in counts.items()},
                    agreement_ratio=0.0,
                    status="pending_more_reviews",
                    final_decision=None,
                    rationale=f"Only {reviewer_count} review(s); waiting for at least {min_reviewers}.",
                )
            )
            continue

        leading_decision, leading_count = top_votes[0]
        agreement_ratio = leading_count / reviewer_count
        if len(top_votes) == 1 or (len(top_votes) > 1 and leading_count > top_votes[1][1]):
            records.append(
                ReviewConsensusRecord(
                    iteration=iteration,
                    reviewer_count=reviewer_count,
                    reviewers=reviewers,
                    vote_counts={decision.value: count for decision, count in counts.items()},
                    agreement_ratio=agreement_ratio,
                    status="consensus",
                    final_decision=leading_decision,
                    rationale=f"Majority consensus reached with agreement ratio {agreement_ratio:.2f}.",
                )
            )
            continue

        final_decision = _most_conservative(counts)
        records.append(
            ReviewConsensusRecord(
                iteration=iteration,
                reviewer_count=reviewer_count,
                reviewers=reviewers,
                vote_counts={decision.value: count for decision, count in counts.items()},
                agreement_ratio=agreement_ratio,
                status="arbitrated",
                final_decision=final_decision,
                rationale="Reviewer conflict detected; defaulting to the most conservative decision.",
            )
        )

    return records


def save_review_consensus(records: list[ReviewConsensusRecord], path: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"records": [item.to_dict() for item in records]}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _most_conservative(counts: Counter[Decision]) -> Decision:
    order = {
        Decision.BLOCK: 3,
        Decision.REVIEW: 2,
        Decision.APPROVE: 1,
    }
    return max(counts.keys(), key=lambda item: order[item])
