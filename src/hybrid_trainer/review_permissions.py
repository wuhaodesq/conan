from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .review_identity import ReviewIdentity


_ALLOWED_DECISIONS = {"approve", "review", "block"}


@dataclass(slots=True)
class ReviewRolePolicy:
    role: str
    allowed_decisions: tuple[str, ...]
    can_resolve: bool
    can_export: bool
    allowed_subjects: tuple[str, ...] = ()
    allowed_groups: tuple[str, ...] = ()
    allowed_emails: tuple[str, ...] = ()
    allowed_issuers: tuple[str, ...] = ()
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "allowed_decisions": list(self.allowed_decisions),
            "can_resolve": self.can_resolve,
            "can_export": self.can_export,
            "allowed_subjects": list(self.allowed_subjects),
            "allowed_groups": list(self.allowed_groups),
            "allowed_emails": list(self.allowed_emails),
            "allowed_issuers": list(self.allowed_issuers),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ReviewRolePolicy":
        decisions = tuple(str(item) for item in payload.get("allowed_decisions", []))
        subjects = tuple(str(item) for item in payload.get("allowed_subjects", []))
        groups = tuple(str(item) for item in payload.get("allowed_groups", []))
        emails = tuple(str(item) for item in payload.get("allowed_emails", []))
        issuers = tuple(str(item) for item in payload.get("allowed_issuers", []))
        invalid = [item for item in decisions if item not in _ALLOWED_DECISIONS]
        if invalid:
            raise ValueError(f"unsupported review decisions: {', '.join(invalid)}")

        return cls(
            role=str(payload["role"]),
            allowed_decisions=decisions,
            can_resolve=bool(payload.get("can_resolve", True)),
            can_export=bool(payload.get("can_export", True)),
            allowed_subjects=subjects,
            allowed_groups=groups,
            allowed_emails=emails,
            allowed_issuers=issuers,
            description=str(payload.get("description", "")),
        )

    def allows_identity(self, identity: ReviewIdentity | None) -> bool:
        if not any((self.allowed_subjects, self.allowed_groups, self.allowed_emails, self.allowed_issuers)):
            return True
        if identity is None:
            return False
        if self.allowed_subjects and identity.subject in self.allowed_subjects:
            return True
        if self.allowed_emails and identity.email and identity.email in self.allowed_emails:
            return True
        if self.allowed_issuers and identity.issuer and identity.issuer in self.allowed_issuers:
            return True
        if self.allowed_groups and any(group in self.allowed_groups for group in identity.groups):
            return True
        return False


@dataclass
class ReviewPermissionPolicy:
    roles: dict[str, ReviewRolePolicy] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "roles": [item.to_dict() for item in self.roles.values()],
        }

    @classmethod
    def default(cls) -> "ReviewPermissionPolicy":
        return cls(
            roles={
                "viewer": ReviewRolePolicy(
                    role="viewer",
                    allowed_decisions=(),
                    can_resolve=False,
                    can_export=False,
                    description="Read-only access for observing queue pressure and past resolutions.",
                ),
                "reviewer": ReviewRolePolicy(
                    role="reviewer",
                    allowed_decisions=("approve", "review", "block"),
                    can_resolve=True,
                    can_export=True,
                    description="Standard human reviewer who can export review decisions for CLI backfill.",
                ),
                "admin": ReviewRolePolicy(
                    role="admin",
                    allowed_decisions=("approve", "review", "block"),
                    can_resolve=True,
                    can_export=True,
                    description="Administrative reviewer with full approval and export rights.",
                ),
            }
        )

    @classmethod
    def from_dict(cls, payload: dict) -> "ReviewPermissionPolicy":
        items = payload.get("roles", payload)
        policy = cls()
        for item in items:
            role_policy = ReviewRolePolicy.from_dict(item)
            policy.roles[role_policy.role] = role_policy
        return policy

    @classmethod
    def from_file(cls, path: str) -> "ReviewPermissionPolicy":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def resolve(self, role: str) -> ReviewRolePolicy:
        if role not in self.roles:
            raise KeyError(f"unknown review role: {role}")
        return self.roles[role]
