from __future__ import annotations

from dataclasses import dataclass, field
import base64
import json
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _coerce_groups(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return (str(value),)


@dataclass(slots=True)
class ReviewIdentity:
    subject: str
    display_name: str = ""
    email: str = ""
    issuer: str = ""
    groups: tuple[str, ...] = ()
    claims: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "display_name": self.display_name,
            "email": self.email,
            "issuer": self.issuer,
            "groups": list(self.groups),
            "claims": self.claims,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ReviewIdentity":
        return cls(
            subject=str(payload.get("subject", "")),
            display_name=str(payload.get("display_name", "")),
            email=str(payload.get("email", "")),
            issuer=str(payload.get("issuer", "")),
            groups=_coerce_groups(payload.get("groups", ())),
            claims=dict(payload.get("claims", {})),
        )

    @classmethod
    def from_claims(
        cls,
        payload: dict,
        *,
        subject_claim: str = "sub",
        display_name_claim: str = "name",
        email_claim: str = "email",
        issuer_claim: str = "iss",
        groups_claim: str = "groups",
    ) -> "ReviewIdentity":
        claims = dict(payload)
        return cls(
            subject=str(claims.get(subject_claim, "")),
            display_name=str(claims.get(display_name_claim, "")),
            email=str(claims.get(email_claim, "")),
            issuer=str(claims.get(issuer_claim, "")),
            groups=_coerce_groups(claims.get(groups_claim, ())),
            claims=claims,
        )


class IdentityProvider(Protocol):
    def resolve(self, token: str) -> ReviewIdentity:
        ...


@dataclass(slots=True)
class StaticIdentityProvider:
    tokens: dict[str, ReviewIdentity] = field(default_factory=dict)
    default_identity: ReviewIdentity | None = None

    def resolve(self, token: str) -> ReviewIdentity:
        if token in self.tokens:
            return self.tokens[token]
        if self.default_identity is not None:
            return self.default_identity
        raise PermissionError("unknown identity token")

    @classmethod
    def from_dict(cls, payload: dict) -> "StaticIdentityProvider":
        tokens_payload = payload.get("tokens", {})
        tokens: dict[str, ReviewIdentity] = {}
        for token, item in tokens_payload.items():
            if isinstance(item, str):
                identity = ReviewIdentity(subject=item, display_name=item, claims={"subject": item})
            elif isinstance(item, dict):
                identity = ReviewIdentity.from_dict(item)
                if not identity.subject:
                    identity.subject = str(token)
                    if not identity.display_name:
                        identity.display_name = identity.subject
            else:
                raise TypeError("static identity tokens must map to strings or objects")
            tokens[str(token)] = identity

        default_identity = payload.get("default_identity")
        return cls(
            tokens=tokens,
            default_identity=ReviewIdentity.from_dict(default_identity) if default_identity else None,
        )


@dataclass(slots=True)
class IntrospectionIdentityProvider:
    introspection_url: str
    client_id: str = ""
    client_secret: str = ""
    timeout_seconds: int = 5
    subject_claim: str = "sub"
    display_name_claim: str = "name"
    email_claim: str = "email"
    groups_claim: str = "groups"
    issuer_claim: str = "iss"
    active_claim: str = "active"

    def resolve(self, token: str) -> ReviewIdentity:
        payload = self._introspect(token)
        if not bool(payload.get(self.active_claim, True)):
            raise PermissionError("identity token is inactive")
        identity = ReviewIdentity.from_claims(
            payload,
            subject_claim=self.subject_claim,
            display_name_claim=self.display_name_claim,
            email_claim=self.email_claim,
            issuer_claim=self.issuer_claim,
            groups_claim=self.groups_claim,
        )
        if not identity.subject:
            raise PermissionError("identity token did not contain a subject claim")
        return identity

    def _introspect(self, token: str) -> dict:
        body = urlencode({"token": token}).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.client_id or self.client_secret:
            credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")
        request = Request(self.introspection_url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:  # pragma: no cover - exercised in integration tests
            raise PermissionError(f"identity introspection failed with HTTP {exc.code}") from exc
        except URLError as exc:  # pragma: no cover - network failures are environment specific
            raise PermissionError(f"identity introspection failed: {exc.reason}") from exc
        if not isinstance(payload, dict):
            raise PermissionError("identity introspection endpoint returned invalid payload")
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "IntrospectionIdentityProvider":
        return cls(
            introspection_url=str(payload["introspection_url"]),
            client_id=str(payload.get("client_id", "")),
            client_secret=str(payload.get("client_secret", "")),
            timeout_seconds=int(payload.get("timeout_seconds", 5)),
            subject_claim=str(payload.get("subject_claim", "sub")),
            display_name_claim=str(payload.get("display_name_claim", "name")),
            email_claim=str(payload.get("email_claim", "email")),
            groups_claim=str(payload.get("groups_claim", "groups")),
            issuer_claim=str(payload.get("issuer_claim", "iss")),
            active_claim=str(payload.get("active_claim", "active")),
        )


def build_identity_provider_from_file(path: str) -> IdentityProvider:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mode = str(payload.get("mode", "static")).lower()
    if mode == "static":
        return StaticIdentityProvider.from_dict(payload)
    if mode in {"introspection", "oidc"}:
        return IntrospectionIdentityProvider.from_dict(payload)
    raise ValueError(f"unsupported identity provider mode: {mode}")
