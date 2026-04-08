from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path

from .decision_console import DecisionConsole
from .human_review import HumanReviewDecision, save_review_decisions
from .review_identity import ReviewIdentity
from .review_permissions import ReviewPermissionPolicy
from .review_router import RoutedReviewBatch


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_session_id() -> str:
    return f"review-session-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


@dataclass(slots=True)
class ReviewerSubmission:
    reviewer: str
    role: str
    decisions: list[HumanReviewDecision]
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "reviewer": self.reviewer,
            "role": self.role,
            "updated_at": self.updated_at,
            "decisions": [item.to_dict() for item in self.decisions],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ReviewerSubmission":
        return cls(
            reviewer=str(payload["reviewer"]),
            role=str(payload["role"]),
            decisions=[HumanReviewDecision.from_dict(item) for item in payload.get("decisions", [])],
            updated_at=str(payload["updated_at"]),
        )


@dataclass
class ReviewSession:
    session_id: str
    created_at: str
    updated_at: str
    review_batch: dict
    console: dict
    permission_policy: dict
    submissions: list[ReviewerSubmission] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        console: DecisionConsole,
        batch: RoutedReviewBatch,
        permission_policy: ReviewPermissionPolicy | None = None,
        session_id: str = "",
    ) -> "ReviewSession":
        now = _timestamp()
        policy = permission_policy or ReviewPermissionPolicy.default()
        return cls(
            session_id=session_id or _default_session_id(),
            created_at=now,
            updated_at=now,
            review_batch={
                "budget": batch.budget,
                "items": [item.to_dict() for item in batch.items],
            },
            console=console.to_dict(),
            permission_policy=policy.to_dict(),
            submissions=[],
        )

    @classmethod
    def from_dict(cls, payload: dict) -> "ReviewSession":
        return cls(
            session_id=str(payload["session_id"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            review_batch=dict(payload["review_batch"]),
            console=dict(payload["console"]),
            permission_policy=dict(payload["permission_policy"]),
            submissions=[ReviewerSubmission.from_dict(item) for item in payload.get("submissions", [])],
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "review_batch": self.review_batch,
            "console": self.console,
            "permission_policy": self.permission_policy,
            "summary": self.summary(),
            "submissions": [item.to_dict() for item in self.submissions],
        }

    def sync_reviewer_submission(
        self,
        reviewer: str,
        role: str,
        decisions: list[HumanReviewDecision],
        identity: ReviewIdentity | None = None,
    ) -> None:
        policy = ReviewPermissionPolicy.from_dict(self.permission_policy)
        role_policy = policy.resolve(role)
        if not role_policy.allows_identity(identity):
            principal = identity.subject if identity is not None else "anonymous"
            raise PermissionError(f"identity {principal} is not allowed to submit role {role}")
        for item in decisions:
            if item.final_decision.value not in role_policy.allowed_decisions:
                raise ValueError(
                    f"reviewer role {role} cannot submit decision {item.final_decision.value}"
                )
            if item.iteration not in self.pending_iterations():
                raise ValueError(f"iteration {item.iteration} is not present in the current review batch")

        submission = ReviewerSubmission(
            reviewer=reviewer,
            role=role,
            decisions=decisions,
            updated_at=_timestamp(),
        )
        self.submissions = [item for item in self.submissions if item.reviewer != reviewer]
        self.submissions.append(submission)
        self.updated_at = submission.updated_at

    def all_decisions(self) -> list[HumanReviewDecision]:
        decisions: list[HumanReviewDecision] = []
        for submission in sorted(self.submissions, key=lambda item: item.updated_at):
            decisions.extend(submission.decisions)
        return decisions

    def pending_iterations(self) -> set[int]:
        return {int(item["iteration"]) for item in self.review_batch.get("items", [])}

    def summary(self) -> dict:
        iterations = self.pending_iterations()
        decisions = self.all_decisions()
        covered_iterations = {item.iteration for item in decisions}
        conflicts = 0
        by_iteration: dict[int, set[str]] = {}
        for item in decisions:
            by_iteration.setdefault(item.iteration, set()).add(item.final_decision.value)
        conflicts = sum(1 for values in by_iteration.values() if len(values) > 1)

        return {
            "session_id": self.session_id,
            "total_reviewers": len(self.submissions),
            "submitted_decisions": len(decisions),
            "pending_iterations": len(iterations),
            "covered_iterations": len(covered_iterations),
            "conflict_iterations": conflicts,
            "reviewers": [
                {
                    "reviewer": item.reviewer,
                    "role": item.role,
                    "decision_count": len(item.decisions),
                    "updated_at": item.updated_at,
                }
                for item in sorted(self.submissions, key=lambda submission: submission.updated_at)
            ],
        }


def load_review_session(path: str) -> ReviewSession:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReviewSession.from_dict(payload)


def save_review_session(session: ReviewSession, path: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def export_review_session_decisions(session: ReviewSession, path: str) -> Path:
    return save_review_decisions(session.all_decisions(), path)


def load_review_decision_payload(path: str) -> tuple[list[HumanReviewDecision], str | None]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("decisions", payload)
    decisions = [HumanReviewDecision.from_dict(item) for item in items]
    role = payload.get("role")
    return decisions, str(role) if role else None
