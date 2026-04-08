from __future__ import annotations

from dataclasses import dataclass, field
import base64
import json
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
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


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass(slots=True)
class OidcPendingLogin:
    state: str
    reviewer_hint: str
    role_hint: str
    redirect_uri: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "reviewer_hint": self.reviewer_hint,
            "role_hint": self.role_hint,
            "redirect_uri": self.redirect_uri,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "OidcPendingLogin":
        return cls(
            state=str(payload["state"]),
            reviewer_hint=str(payload.get("reviewer_hint", "")),
            role_hint=str(payload.get("role_hint", "")),
            redirect_uri=str(payload.get("redirect_uri", "")),
            created_at=str(payload.get("created_at", _timestamp())),
        )


@dataclass(slots=True)
class OidcSessionRecord:
    session_token: str
    state: str
    reviewer_hint: str
    role_hint: str
    redirect_uri: str
    identity: dict
    access_token: str
    refresh_token: str
    expires_at: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "session_token": self.session_token,
            "state": self.state,
            "reviewer_hint": self.reviewer_hint,
            "role_hint": self.role_hint,
            "redirect_uri": self.redirect_uri,
            "identity": self.identity,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "OidcSessionRecord":
        return cls(
            session_token=str(payload["session_token"]),
            state=str(payload.get("state", "")),
            reviewer_hint=str(payload.get("reviewer_hint", "")),
            role_hint=str(payload.get("role_hint", "")),
            redirect_uri=str(payload.get("redirect_uri", "")),
            identity=dict(payload.get("identity", {})),
            access_token=str(payload.get("access_token", "")),
            refresh_token=str(payload.get("refresh_token", "")),
            expires_at=str(payload.get("expires_at", _timestamp())),
            created_at=str(payload.get("created_at", _timestamp())),
            updated_at=str(payload.get("updated_at", _timestamp())),
        )


@dataclass(slots=True)
class OidcAuthorizationCodeIdentityProvider:
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    client_id: str
    client_secret: str = ""
    scope: str = "openid profile email"
    timeout_seconds: int = 5
    refresh_margin_seconds: int = 30
    session_cache_path: str = ""
    subject_claim: str = "sub"
    display_name_claim: str = "name"
    email_claim: str = "email"
    groups_claim: str = "groups"
    issuer_claim: str = "iss"
    active_claim: str = "active"
    pending_logins: dict[str, OidcPendingLogin] = field(default_factory=dict, init=False, repr=False)
    sessions: dict[str, OidcSessionRecord] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._load_session_cache()

    def start_login(self, reviewer_hint: str = "", role_hint: str = "", redirect_uri: str = "") -> dict:
        if not redirect_uri:
            raise ValueError("redirect_uri is required to start an oidc login")
        state = secrets.token_urlsafe(16)
        pending = OidcPendingLogin(
            state=state,
            reviewer_hint=reviewer_hint,
            role_hint=role_hint,
            redirect_uri=redirect_uri,
            created_at=_timestamp(),
        )
        self.pending_logins[state] = pending
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.scope,
            "state": state,
        }
        if reviewer_hint:
            params["login_hint"] = reviewer_hint
        return {
            "state": state,
            "authorization_url": f"{self.authorization_endpoint}?{urlencode(params)}",
            "redirect_uri": redirect_uri,
            "reviewer_hint": reviewer_hint,
            "role_hint": role_hint,
        }

    def complete_login(self, code: str, state: str) -> dict:
        pending = self.pending_logins.pop(state, None)
        if pending is None:
            raise PermissionError("unknown or expired oidc login state")
        token_payload = self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": pending.redirect_uri,
            }
        )
        record = self._build_session_record(token_payload, pending, state)
        self.sessions[record.session_token] = record
        self._save_session_cache()
        return {
            "session_token": record.session_token,
            "identity": record.identity,
            "state": record.state,
            "reviewer_hint": record.reviewer_hint,
            "role_hint": record.role_hint,
            "expires_at": record.expires_at,
        }

    def resolve(self, token: str) -> ReviewIdentity:
        record = self.sessions.get(token)
        if record is None:
            raise PermissionError("unknown oidc session token")
        record = self._refresh_if_needed(record)
        return ReviewIdentity.from_dict(record.identity)

    def describe_session(self, token: str) -> dict:
        record = self.sessions.get(token)
        if record is None:
            raise KeyError(f"unknown oidc session token: {token}")
        return record.to_dict()

    def _build_session_record(self, token_payload: dict, pending: OidcPendingLogin, state: str) -> OidcSessionRecord:
        access_token = str(token_payload.get("access_token", ""))
        if not access_token:
            raise PermissionError("oidc token response did not include an access token")
        refresh_token = str(token_payload.get("refresh_token", ""))
        expires_in = int(token_payload.get("expires_in", 300))
        identity = self._fetch_identity(access_token)
        session_token = secrets.token_urlsafe(32)
        now = _timestamp()
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        return OidcSessionRecord(
            session_token=session_token,
            state=state,
            reviewer_hint=pending.reviewer_hint,
            role_hint=pending.role_hint,
            redirect_uri=pending.redirect_uri,
            identity=identity.to_dict(),
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )

    def _refresh_if_needed(self, record: OidcSessionRecord) -> OidcSessionRecord:
        expires_at = datetime.fromisoformat(record.expires_at)
        if datetime.now(timezone.utc) < expires_at - timedelta(seconds=self.refresh_margin_seconds):
            return record
        if not record.refresh_token:
            raise PermissionError("oidc session expired and no refresh token is available")

        token_payload = self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": record.refresh_token,
            }
        )
        access_token = str(token_payload.get("access_token", record.access_token))
        refresh_token = str(token_payload.get("refresh_token", record.refresh_token))
        expires_in = int(token_payload.get("expires_in", 300))
        identity = self._fetch_identity(access_token)
        record.access_token = access_token
        record.refresh_token = refresh_token
        record.expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        record.identity = identity.to_dict()
        record.updated_at = _timestamp()
        self.sessions[record.session_token] = record
        self._save_session_cache()
        return record

    def _fetch_identity(self, access_token: str) -> ReviewIdentity:
        request = Request(
            self.userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:  # pragma: no cover - exercised in integration tests
            raise PermissionError(f"oidc userinfo request failed with HTTP {exc.code}") from exc
        except URLError as exc:  # pragma: no cover - network failures are environment specific
            raise PermissionError(f"oidc userinfo request failed: {exc.reason}") from exc
        if not isinstance(payload, dict):
            raise PermissionError("oidc userinfo endpoint returned invalid payload")
        if not bool(payload.get(self.active_claim, True)):
            raise PermissionError("oidc userinfo payload marked the identity inactive")
        identity = ReviewIdentity.from_claims(
            payload,
            subject_claim=self.subject_claim,
            display_name_claim=self.display_name_claim,
            email_claim=self.email_claim,
            issuer_claim=self.issuer_claim,
            groups_claim=self.groups_claim,
        )
        if not identity.subject:
            raise PermissionError("oidc userinfo payload did not contain a subject claim")
        return identity

    def _token_request(self, data: dict[str, str]) -> dict:
        payload = {
            **data,
            "client_id": self.client_id,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.client_secret:
            credentials = f"{self.client_id}:{self.client_secret}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")
        request = Request(
            self.token_endpoint,
            data=urlencode(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                token_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:  # pragma: no cover - exercised in integration tests
            raise PermissionError(f"oidc token exchange failed with HTTP {exc.code}") from exc
        except URLError as exc:  # pragma: no cover - network failures are environment specific
            raise PermissionError(f"oidc token exchange failed: {exc.reason}") from exc
        if not isinstance(token_payload, dict):
            raise PermissionError("oidc token endpoint returned invalid payload")
        return token_payload

    def _load_session_cache(self) -> None:
        if not self.session_cache_path:
            return
        source = Path(self.session_cache_path)
        if not source.exists():
            return
        payload = json.loads(source.read_text(encoding="utf-8"))
        self.sessions = {
            str(item["session_token"]): OidcSessionRecord.from_dict(item)
            for item in payload.get("sessions", [])
        }

    def _save_session_cache(self) -> None:
        if not self.session_cache_path:
            return
        output = Path(self.session_cache_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": [item.to_dict() for item in self.sessions.values()],
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, payload: dict) -> "OidcAuthorizationCodeIdentityProvider":
        return cls(
            authorization_endpoint=str(payload["authorization_endpoint"]),
            token_endpoint=str(payload["token_endpoint"]),
            userinfo_endpoint=str(payload["userinfo_endpoint"]),
            client_id=str(payload["client_id"]),
            client_secret=str(payload.get("client_secret", "")),
            scope=str(payload.get("scope", "openid profile email")),
            timeout_seconds=int(payload.get("timeout_seconds", 5)),
            refresh_margin_seconds=int(payload.get("refresh_margin_seconds", 30)),
            session_cache_path=str(payload.get("session_cache_path", "")),
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
    if mode in {"authorization_code", "oidc_authorization_code", "auth_code"}:
        return OidcAuthorizationCodeIdentityProvider.from_dict(payload)
    raise ValueError(f"unsupported identity provider mode: {mode}")
