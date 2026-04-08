import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import parse_qs

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.review_identity import (
    OidcAuthorizationCodeIdentityProvider,
    IntrospectionIdentityProvider,
    ReviewIdentity,
    StaticIdentityProvider,
    build_identity_provider_from_file,
)
from hybrid_trainer.review_permissions import ReviewPermissionPolicy
from hybrid_trainer.review_router import route_review_items
from hybrid_trainer.review_server import build_review_server
from hybrid_trainer.review_session import ReviewSession, save_review_session
from hybrid_trainer.review_store import build_review_store


def _request_json(url: str, token: str = "", method: str = "GET", payload: dict | None = None) -> dict:
    body = None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


class _IntrospectionHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/introspect":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        token = parse_qs(raw).get("token", [""])[0]
        payload = self.server.identity_payloads.get(token, {"active": False})  # type: ignore[attr-defined]
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def _start_introspection_server(identity_payloads: dict[str, dict]) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _IntrospectionHandler)
    server.identity_payloads = identity_payloads  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class _OidcAuthorizationHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = parse_qs(self.path.split("?", 1)[1] if "?" in self.path else "")
        if self.path.startswith("/authorize"):
            login_hint = parsed.get("login_hint", ["alice"])[0]
            state = parsed.get("state", [""])[0]
            redirect_uri = parsed.get("redirect_uri", [""])[0]
            claims = self.server.claims_by_hint.get(login_hint, self.server.default_claims)  # type: ignore[attr-defined]
            code = f"code-{len(self.server.authorization_codes) + 1}"  # type: ignore[attr-defined]
            self.server.authorization_codes[code] = claims  # type: ignore[attr-defined]
            separator = "&" if "?" in redirect_uri else "?"
            location = f"{redirect_uri}{separator}code={code}&state={state}"
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()
            return
        if self.path.startswith("/userinfo"):
            auth = self.headers.get("Authorization", "")
            token = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
            claims = self.server.access_tokens.get(token)  # type: ignore[attr-defined]
            if claims is None:
                self.send_response(401)
                self.end_headers()
                return
            body = json.dumps(claims).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/token"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        payload = parse_qs(body)
        grant_type = payload.get("grant_type", [""])[0]
        if grant_type == "authorization_code":
            code = payload.get("code", [""])[0]
            claims = self.server.authorization_codes.pop(code, None)  # type: ignore[attr-defined]
            if claims is None:
                self.send_response(400)
                self.end_headers()
                return
            access_token = f"access-{len(self.server.access_tokens) + 1}"  # type: ignore[attr-defined]
            refresh_token = f"refresh-{len(self.server.refresh_tokens) + 1}"  # type: ignore[attr-defined]
            self.server.access_tokens[access_token] = claims  # type: ignore[attr-defined]
            self.server.refresh_tokens[refresh_token] = claims  # type: ignore[attr-defined]
            response = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": self.server.expires_in_seconds,  # type: ignore[attr-defined]
            }
        elif grant_type == "refresh_token":
            refresh_token = payload.get("refresh_token", [""])[0]
            claims = self.server.refresh_tokens.get(refresh_token)  # type: ignore[attr-defined]
            if claims is None:
                self.send_response(400)
                self.end_headers()
                return
            self.server.refresh_count += 1  # type: ignore[attr-defined]
            access_token = f"refreshed-access-{self.server.refresh_count}"  # type: ignore[attr-defined]
            next_refresh = f"refreshed-refresh-{self.server.refresh_count}"  # type: ignore[attr-defined]
            self.server.access_tokens[access_token] = claims  # type: ignore[attr-defined]
            self.server.refresh_tokens[next_refresh] = claims  # type: ignore[attr-defined]
            response = {
                "access_token": access_token,
                "refresh_token": next_refresh,
                "token_type": "Bearer",
                "expires_in": self.server.expires_in_seconds,  # type: ignore[attr-defined]
            }
        else:
            self.send_response(400)
            self.end_headers()
            return
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def _start_oidc_authorization_server(
    claims_by_hint: dict[str, dict],
    expires_in_seconds: int = 1,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OidcAuthorizationHandler)
    server.claims_by_hint = claims_by_hint  # type: ignore[attr-defined]
    server.default_claims = next(iter(claims_by_hint.values()))  # type: ignore[attr-defined]
    server.authorization_codes = {}  # type: ignore[attr-defined]
    server.access_tokens = {}  # type: ignore[attr-defined]
    server.refresh_tokens = {}  # type: ignore[attr-defined]
    server.refresh_count = 0  # type: ignore[attr-defined]
    server.expires_in_seconds = expires_in_seconds  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_static_identity_provider_and_group_permissions(tmp_path) -> None:
    config = tmp_path / "identity_provider.json"
    config.write_text(
        json.dumps(
            {
                "mode": "static",
                "tokens": {
                    "triager-token": {
                        "subject": "alice",
                        "display_name": "Alice Example",
                        "email": "alice@example.com",
                        "groups": ["triagers"],
                    },
                    "observer-token": {
                        "subject": "bob",
                        "display_name": "Bob Observer",
                        "email": "bob@example.com",
                        "groups": ["observers"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    provider = build_identity_provider_from_file(str(config))
    assert isinstance(provider, StaticIdentityProvider)

    triager = provider.resolve("triager-token")
    observer = provider.resolve("observer-token")

    policy = ReviewPermissionPolicy.from_dict(
        {
            "roles": [
                {
                    "role": "triager",
                    "allowed_decisions": ["approve", "review"],
                    "can_resolve": True,
                    "can_export": True,
                    "allowed_groups": ["triagers"],
                    "description": "Group-restricted triager role.",
                }
            ]
        }
    )

    role_policy = policy.resolve("triager")
    assert role_policy.allows_identity(triager) is True
    assert role_policy.allows_identity(observer) is False


def test_review_role_policy_matches_subject_email_and_issuer() -> None:
    policy = ReviewPermissionPolicy.from_dict(
        {
            "roles": [
                {
                    "role": "triager",
                    "allowed_decisions": ["approve", "review"],
                    "can_resolve": True,
                    "can_export": True,
                    "allowed_subjects": ["alice"],
                    "allowed_emails": ["alice@example.com"],
                    "allowed_issuers": ["local-dev"],
                    "allowed_groups": ["triagers"],
                }
            ]
        }
    )
    role_policy = policy.resolve("triager")
    allowed = ReviewIdentity(
        subject="alice",
        display_name="Alice Example",
        email="alice@example.com",
        issuer="local-dev",
        groups=("triagers",),
    )
    matched_by_email = ReviewIdentity(
        subject="eve",
        display_name="Eve Example",
        email="alice@example.com",
        issuer="other-issuer",
        groups=("other",),
    )
    rejected = ReviewIdentity(
        subject="eve",
        display_name="Eve Example",
        email="eve@other.example",
        issuer="other-issuer",
        groups=("other",),
    )

    assert role_policy.allows_identity(allowed) is True
    assert role_policy.allows_identity(matched_by_email) is True
    assert role_policy.allows_identity(rejected) is False


def test_example_identity_and_permission_configs_parse() -> None:
    static_provider = build_identity_provider_from_file("examples/identity_provider_static.json")
    oidc_provider = build_identity_provider_from_file("examples/identity_provider_oidc.json")
    oidc_auth_code_provider = build_identity_provider_from_file("examples/identity_provider_oidc_auth_code.json")
    policy = ReviewPermissionPolicy.from_file("examples/review_permissions_identity.json")

    assert isinstance(static_provider, StaticIdentityProvider)
    assert isinstance(oidc_provider, IntrospectionIdentityProvider)
    assert isinstance(oidc_auth_code_provider, OidcAuthorizationCodeIdentityProvider)
    triager = policy.resolve("triager")
    assert triager.allowed_subjects == ("alice",)
    assert triager.allowed_emails == ("alice@example.com",)
    assert triager.allowed_issuers == ("local-dev",)
    assert triager.allowed_groups == ("triagers",)


def test_introspection_identity_provider_and_review_server_permissions(tmp_path) -> None:
    introspection_server, introspection_thread = _start_introspection_server(
        {
            "triager-token": {
                "active": True,
                "sub": "alice",
                "name": "Alice Example",
                "email": "alice@example.com",
                "groups": ["triagers"],
                "iss": "https://idp.example.test",
            },
            "observer-token": {
                "active": True,
                "sub": "bob",
                "name": "Bob Observer",
                "email": "bob@example.com",
                "groups": ["observers"],
                "iss": "https://idp.example.test",
            },
            "admin-token": {
                "active": True,
                "sub": "carol",
                "name": "Carol Admin",
                "email": "carol@example.com",
                "groups": ["admins"],
                "iss": "https://idp.example.test",
            },
        }
    )
    try:
        introspection_url = f"http://127.0.0.1:{introspection_server.server_address[1]}/introspect"
        provider = IntrospectionIdentityProvider(introspection_url=introspection_url, timeout_seconds=5)
        identity = provider.resolve("triager-token")
        assert identity.subject == "alice"
        assert identity.groups == ("triagers",)

        engine = TrainingEngine()
        engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
        console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
        batch = route_review_items(engine.review_queue.pending, budget=2)
        session_path = tmp_path / "review_session.json"
        audit_log = tmp_path / "review_audit.jsonl"
        save_review_session(
            ReviewSession.create(
                console=console,
                batch=batch,
                permission_policy=ReviewPermissionPolicy.from_dict(
                    {
                        "roles": [
                            {
                                "role": "viewer",
                                "allowed_decisions": [],
                                "can_resolve": False,
                                "can_export": False,
                            },
                            {
                                "role": "triager",
                                "allowed_decisions": ["approve", "review"],
                                "can_resolve": True,
                                "can_export": True,
                                "allowed_groups": ["triagers"],
                            },
                            {
                                "role": "admin",
                                "allowed_decisions": ["approve", "review", "block"],
                                "can_resolve": True,
                                "can_export": True,
                                "allowed_groups": ["admins"],
                            },
                        ]
                    }
                ),
            ),
            str(session_path),
        )

        store = build_review_store(session_path=str(session_path), audit_log_path=str(audit_log))
        server = build_review_server(
            auth_token="",
            store=store,
            identity_provider=provider,
            host="127.0.0.1",
            port=0,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            with urlopen(  # noqa: S310
                Request(
                    f"{base_url}/?token=triager-token&reviewer=alice&role=triager",
                    headers={"Authorization": "Bearer triager-token"},
                ),
                timeout=5,
            ) as response:
                html = response.read().decode("utf-8")
            assert "Identity API" in html
            assert "Alice Example" in html

            session_payload = _request_json(f"{base_url}/api/session", token="triager-token")
            assert session_payload["identity"]["subject"] == "alice"

            first_iteration = session_payload["review_batch"]["items"][0]["iteration"]
            submit_payload = _request_json(
                f"{base_url}/api/decisions",
                token="triager-token",
                method="POST",
                payload={
                    "reviewer": "alice",
                    "role": "triager",
                    "decisions": [
                        {
                            "iteration": first_iteration,
                            "final_decision": "approve",
                            "reviewer": "alice",
                            "note": "approved by identity-backed reviewer",
                        }
                    ],
                },
            )
            assert submit_payload["summary"]["submitted_decisions"] == 1
            assert submit_payload["identity"]["subject"] == "alice"

            try:
                _request_json(
                    f"{base_url}/api/decisions",
                    token="observer-token",
                    method="POST",
                    payload={
                        "reviewer": "bob",
                        "role": "triager",
                        "decisions": [
                            {
                                "iteration": first_iteration,
                                "final_decision": "review",
                                "reviewer": "bob",
                                "note": "should be blocked by group policy",
                            }
                        ],
                    },
                )
                assert False, "expected the observer identity to be rejected"
            except HTTPError as exc:
                assert exc.code == 403

            audit_payload = _request_json(f"{base_url}/api/audit?role=admin", token="admin-token")
            assert audit_payload["identity"]["subject"] == "carol"
            assert audit_payload["events"][0]["actor"] == "Alice Example"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    finally:
        introspection_server.shutdown()
        introspection_server.server_close()
        introspection_thread.join(timeout=5)


def test_oidc_authorization_code_flow_refreshes_session_tokens(tmp_path) -> None:
    oidc_server, oidc_thread = _start_oidc_authorization_server(
        {
            "alice": {
                "sub": "alice",
                "name": "Alice Example",
                "email": "alice@example.com",
                "groups": ["triagers"],
                "iss": "https://idp.example.test",
                "active": True,
            }
        },
        expires_in_seconds=1,
    )
    try:
        auth_base = f"http://127.0.0.1:{oidc_server.server_address[1]}"
        provider_config = tmp_path / "identity_provider_oidc_auth_code.json"
        session_cache = tmp_path / "oidc_sessions.json"
        provider_config.write_text(
            json.dumps(
                {
                    "mode": "authorization_code",
                    "authorization_endpoint": f"{auth_base}/authorize",
                    "token_endpoint": f"{auth_base}/token",
                    "userinfo_endpoint": f"{auth_base}/userinfo",
                    "client_id": "hybrid-trainer",
                    "client_secret": "replace-me",
                    "scope": "openid profile email",
                    "timeout_seconds": 5,
                    "refresh_margin_seconds": 5,
                    "session_cache_path": str(session_cache),
                    "subject_claim": "sub",
                    "display_name_claim": "name",
                    "email_claim": "email",
                    "groups_claim": "groups",
                    "issuer_claim": "iss",
                    "active_claim": "active",
                }
            ),
            encoding="utf-8",
        )
        provider = build_identity_provider_from_file(str(provider_config))
        assert isinstance(provider, OidcAuthorizationCodeIdentityProvider)

        engine = TrainingEngine()
        engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
        console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
        batch = route_review_items(engine.review_queue.pending, budget=2)
        session_path = tmp_path / "review_session.json"
        audit_log = tmp_path / "review_audit.jsonl"
        save_review_session(
            ReviewSession.create(
                console=console,
                batch=batch,
                permission_policy=ReviewPermissionPolicy.from_dict(
                    {
                        "roles": [
                            {
                                "role": "triager",
                                "allowed_decisions": ["approve", "review"],
                                "can_resolve": True,
                                "can_export": True,
                                "allowed_subjects": ["alice"],
                                "allowed_groups": ["triagers"],
                            },
                            {
                                "role": "admin",
                                "allowed_decisions": ["approve", "review", "block"],
                                "can_resolve": True,
                                "can_export": True,
                                "allowed_groups": ["admins"],
                            },
                        ]
                    }
                ),
            ),
            str(session_path),
        )

        store = build_review_store(session_path=str(session_path), audit_log_path=str(audit_log))
        server = build_review_server(
            auth_token="",
            store=store,
            identity_provider=provider,
            host="127.0.0.1",
            port=0,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            login_payload = _request_json(f"{base_url}/api/oidc/login?reviewer=alice&role=triager")
            assert login_payload["authorization_url"].startswith(f"{auth_base}/authorize")

            callback_payload = _request_json(login_payload["authorization_url"])
            assert callback_payload["identity"]["subject"] == "alice"
            session_token = callback_payload["session_token"]

            session_payload = _request_json(f"{base_url}/api/session", token=session_token)
            assert session_payload["identity"]["subject"] == "alice"

            session_snapshot = provider.describe_session(session_token)
            assert session_snapshot["access_token"].startswith("refreshed-access-")
            assert oidc_server.refresh_count >= 1
            assert session_cache.exists()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    finally:
        oidc_server.shutdown()
        oidc_server.server_close()
        oidc_thread.join(timeout=5)
