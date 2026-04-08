from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from .human_review import HumanReviewDecision
from .review_audit import create_review_audit_event
from .review_identity import (
    IdentityProvider,
    OidcAuthorizationCodeIdentityProvider,
    ReviewIdentity,
    build_identity_provider_from_file,
)
from .review_permissions import ReviewPermissionPolicy
from .review_session import ReviewSession
from .review_store import ReviewStore, build_review_store


def build_review_server(
    session_path: str = "",
    auth_token: str = "",
    audit_log_path: str = "",
    postgres_dsn: str = "",
    host: str = "127.0.0.1",
    port: int = 8000,
    store: ReviewStore | None = None,
    identity_provider: IdentityProvider | None = None,
) -> ThreadingHTTPServer:
    app = ReviewServerApp(
        auth_token=auth_token,
        store=store
        or build_review_store(
            session_path=session_path,
            audit_log_path=audit_log_path,
            postgres_dsn=postgres_dsn,
        ),
        identity_provider=identity_provider,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            app.handle(self)

        def do_POST(self) -> None:  # noqa: N802
            app.handle(self)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    server.review_app = app  # type: ignore[attr-defined]
    return server


def serve_review_server(
    session_path: str = "",
    auth_token: str = "",
    audit_log_path: str = "",
    postgres_dsn: str = "",
    host: str = "127.0.0.1",
    port: int = 8000,
    store: ReviewStore | None = None,
    identity_provider: IdentityProvider | None = None,
) -> None:
    server = build_review_server(
        session_path=session_path,
        auth_token=auth_token,
        audit_log_path=audit_log_path,
        postgres_dsn=postgres_dsn,
        host=host,
        port=port,
        store=store,
        identity_provider=identity_provider,
    )
    with server:
        server.serve_forever()


class ReviewServerApp:
    def __init__(
        self,
        auth_token: str,
        store: ReviewStore,
        identity_provider: IdentityProvider | None = None,
    ) -> None:
        self.auth_token = auth_token
        self.store = store
        self.identity_provider = identity_provider
        self._lock = threading.Lock()

    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if handler.command == "GET" and parsed.path == "/api/oidc/login":
            self._handle_oidc_login(handler, parsed)
            return
        if handler.command == "GET" and parsed.path == "/api/oidc/callback":
            self._handle_oidc_callback(handler, parsed)
            return
        identity = self._authenticate(handler, parsed)
        if identity is None:
            self._send_json(handler, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        if handler.command == "GET" and parsed.path == "/":
            self._send_html(handler, self._render_index(parsed, identity))
            return
        if handler.command == "GET" and parsed.path == "/api/identity":
            self._send_json(handler, HTTPStatus.OK, identity.to_dict())
            return
        if handler.command == "GET" and parsed.path == "/api/session":
            session = self.store.load_session()
            payload = session.to_dict()
            payload["identity"] = identity.to_dict()
            self._send_json(handler, HTTPStatus.OK, payload)
            return
        if handler.command == "GET" and parsed.path == "/api/audit":
            role = _query_value(parsed, "role", "viewer")
            session = self.store.load_session()
            policy = ReviewPermissionPolicy.from_dict(session.permission_policy)
            if role != "admin":
                self._send_json(handler, HTTPStatus.FORBIDDEN, {"error": "admin role required"})
                return
            role_policy = policy.resolve(role)
            if self.identity_provider is not None and not role_policy.allows_identity(identity):
                self._send_json(handler, HTTPStatus.FORBIDDEN, {"error": "identity not permitted for admin audit access"})
                return
            events = [item.to_dict() for item in self.store.load_audit_events()]
            self._send_json(handler, HTTPStatus.OK, {"events": events, "identity": identity.to_dict()})
            return
        if handler.command == "POST" and parsed.path == "/api/decisions":
            try:
                payload = self._read_json(handler)
                reviewer = str(payload.get("reviewer", identity.subject))
                role = str(payload["role"])
                decisions = [HumanReviewDecision.from_dict(item) for item in payload.get("decisions", [])]
                audit_identity = (
                    identity
                    if self.identity_provider is not None
                    else ReviewIdentity(subject=reviewer, display_name=reviewer, claims={"auth_mode": "shared-token"})
                )
                if self.identity_provider is not None and reviewer != identity.subject:
                    raise PermissionError(
                        f"submitted reviewer {reviewer!r} does not match authenticated identity {identity.subject!r}"
                    )
                session = self.store.load_session()
                policy = ReviewPermissionPolicy.from_dict(session.permission_policy)
                role_policy = policy.resolve(role)
                if self.identity_provider is not None and not role_policy.allows_identity(identity):
                    raise PermissionError(f"identity {identity.subject!r} is not allowed to use role {role!r}")
                with self._lock:
                    session = self.store.load_session()
                    session.sync_reviewer_submission(
                        reviewer=reviewer,
                        role=role,
                        decisions=decisions,
                        identity=identity if self.identity_provider is not None else None,
                    )
                    self.store.save_session(session)
                    self.store.append_audit_event(
                        create_review_audit_event(
                            action="decisions_submitted",
                            actor=audit_identity.display_name or audit_identity.subject,
                            role=role,
                            session_id=session.session_id,
                            payload={
                                "decision_count": len(decisions),
                                "iterations": [item.iteration for item in decisions],
                                "identity": audit_identity.to_dict(),
                            },
                        ),
                    )
            except PermissionError as exc:
                self._send_json(handler, HTTPStatus.FORBIDDEN, {"error": str(exc)})
                return
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                self._send_json(handler, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._send_json(
                handler,
                HTTPStatus.OK,
                {**session.to_dict(), "identity": identity.to_dict()},
            )
            return

        self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _handle_oidc_login(self, handler: BaseHTTPRequestHandler, parsed) -> None:
        provider = self._oidc_auth_code_provider()
        if provider is None:
            self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "oidc authorization code flow is not enabled"})
            return
        reviewer = _query_value(parsed, "reviewer", "web_reviewer")
        role = _query_value(parsed, "role", "reviewer")
        callback_url = self._build_callback_url(handler)
        payload = provider.start_login(
            reviewer_hint=reviewer,
            role_hint=role,
            redirect_uri=callback_url,
        )
        self._send_json(handler, HTTPStatus.OK, payload)

    def _handle_oidc_callback(self, handler: BaseHTTPRequestHandler, parsed) -> None:
        provider = self._oidc_auth_code_provider()
        if provider is None:
            self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "oidc authorization code flow is not enabled"})
            return
        code = _query_value(parsed, "code", "")
        state = _query_value(parsed, "state", "")
        if not code or not state:
            self._send_json(handler, HTTPStatus.BAD_REQUEST, {"error": "code and state are required"})
            return
        try:
            payload = provider.complete_login(code=code, state=state)
        except PermissionError as exc:
            self._send_json(handler, HTTPStatus.FORBIDDEN, {"error": str(exc)})
            return
        self._send_json(handler, HTTPStatus.OK, payload)

    def _authenticate(self, handler: BaseHTTPRequestHandler, parsed) -> ReviewIdentity | None:
        header = handler.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[len("Bearer "):]
        else:
            token = _query_value(parsed, "token", "")
        if not token:
            return None
        oidc_provider = self._oidc_auth_code_provider()
        if oidc_provider is not None:
            try:
                return oidc_provider.resolve(token)
            except PermissionError:
                return None
        if self.identity_provider is not None:
            try:
                return self.identity_provider.resolve(token)
            except PermissionError:
                return None
        if not self.auth_token or not secrets.compare_digest(token, self.auth_token):
            return None
        reviewer = _query_value(parsed, "reviewer", "reviewer")
        return ReviewIdentity(
            subject=reviewer,
            display_name=reviewer,
            claims={"auth_mode": "shared-token"},
        )

    def _oidc_auth_code_provider(self) -> OidcAuthorizationCodeIdentityProvider | None:
        if isinstance(self.identity_provider, OidcAuthorizationCodeIdentityProvider):
            return self.identity_provider
        return None

    def _build_callback_url(self, handler: BaseHTTPRequestHandler) -> str:
        host = handler.headers.get("Host")
        if not host:
            server_host, server_port = handler.server.server_address  # type: ignore[attr-defined]
            host = f"{server_host}:{server_port}"
        return f"http://{host}/api/oidc/callback"

    def _read_json(self, handler: BaseHTTPRequestHandler) -> dict:
        length = int(handler.headers.get("Content-Length", "0"))
        raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _render_index(self, parsed, identity: ReviewIdentity) -> str:
        reviewer = identity.display_name or identity.subject or _query_value(parsed, "reviewer", "web_reviewer")
        role = _query_value(parsed, "role", "reviewer")
        token = _query_value(parsed, "token", "")
        session = self.store.load_session()
        identity_payload = json.dumps(identity.to_dict(), ensure_ascii=False)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hybrid Trainer Review Server</title>
  <style>
    :root {{
      --bg: #f4f0e8;
      --panel: rgba(255,255,255,0.9);
      --ink: #21302b;
      --muted: #5f706b;
      --accent: #9d4f2c;
      --line: rgba(33, 48, 43, 0.12);
    }}
    body {{
      margin: 0;
      background: linear-gradient(135deg, #f6f2ea 0%, #edf3ec 100%);
      color: var(--ink);
      font-family: "Trebuchet MS", Verdana, sans-serif;
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 22px;
      margin-top: 18px;
    }}
    h1, h2 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
    }}
    p {{
      color: var(--muted);
      line-height: 1.7;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
    }}
    th, td {{
      text-align: left;
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    select, textarea, button {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      font: inherit;
      background: rgba(255,255,255,0.85);
    }}
    textarea {{
      min-height: 82px;
      resize: vertical;
    }}
    button {{
      margin-top: 14px;
      background: linear-gradient(135deg, var(--accent) 0%, #c86a3d 100%);
      color: white;
      border: none;
      font-weight: 600;
      cursor: pointer;
    }}
    pre {{
      margin-top: 16px;
      padding: 16px;
      border-radius: 16px;
      background: #1f2825;
      color: #eff5f0;
      overflow-x: auto;
    }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>Review Server Workbench</h1>
      <p>Authenticated server-side review session for {reviewer} ({role}). Session: {session.session_id}</p>
      <p>Identity-backed access uses the configured provider when present; otherwise the legacy shared bearer token flow remains available.</p>
    </section>
    <section class="panel">
      <h2>Session API</h2>
      <pre id="session-json">loading...</pre>
    </section>
    <section class="panel">
      <h2>Identity API</h2>
      <pre id="identity-json">loading...</pre>
    </section>
    <section class="panel">
      <h2>Submit Decisions</h2>
      <table>
        <thead>
          <tr><th>Iteration</th><th>Decision</th><th>Note</th></tr>
        </thead>
        <tbody>
          {_decision_rows(session)}
        </tbody>
      </table>
      <button id="submit">Submit Decisions</button>
      <pre id="submit-result">waiting...</pre>
    </section>
  </main>
  <script>
    const identity = {identity_payload};
    const authToken = {json.dumps(token)};
    const reviewer = identity.subject || {json.dumps(reviewer)};
    const role = {json.dumps(role)};

    async function loadSession() {{
      const response = await fetch('/api/session', {{
        headers: {{ Authorization: `Bearer ${{authToken}}` }}
      }});
      const payload = await response.json();
      document.getElementById('session-json').textContent = JSON.stringify(payload.summary || payload, null, 2);
    }}

    async function loadIdentity() {{
      const response = await fetch('/api/identity', {{
        headers: {{ Authorization: `Bearer ${{authToken}}` }}
      }});
      const payload = await response.json();
      document.getElementById('identity-json').textContent = JSON.stringify(payload, null, 2);
    }}

    async function submitDecisions() {{
      const rows = Array.from(document.querySelectorAll('[data-iteration]'));
      const decisions = rows.flatMap((row) => {{
        const select = row.querySelector('select');
        const note = row.querySelector('textarea');
        if (!select || !select.value) {{
          return [];
        }}
        return [{{
          iteration: Number(row.dataset.iteration),
          final_decision: select.value,
          reviewer,
          note: note ? note.value : '',
        }}];
      }});
      const response = await fetch('/api/decisions', {{
        method: 'POST',
        headers: {{
          Authorization: `Bearer ${{authToken}}`,
          'Content-Type': 'application/json',
        }},
        body: JSON.stringify({{ reviewer, role, decisions }}),
      }});
      const payload = await response.json();
      document.getElementById('submit-result').textContent = JSON.stringify(payload, null, 2);
      await loadSession();
      await loadIdentity();
    }}

    document.getElementById('submit').addEventListener('click', submitDecisions);
    loadSession();
    loadIdentity();
  </script>
</body>
</html>
"""

    def _send_json(self, handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _send_html(self, handler: BaseHTTPRequestHandler, html: str) -> None:
        body = html.encode("utf-8")
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


def _query_value(parsed, key: str, default: str) -> str:
    return parse_qs(parsed.query).get(key, [default])[0]


def _decision_rows(session: ReviewSession) -> str:
    rows = []
    for item in session.review_batch.get("items", []):
        iteration = int(item["iteration"])
        rows.append(
            f'<tr data-iteration="{iteration}">'
            f"<td>{iteration}</td>"
            '<td><select><option value="">Select decision</option><option value="approve">approve</option><option value="review">review</option><option value="block">block</option></select></td>'
            '<td><textarea placeholder="optional reviewer note"></textarea></td>'
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="3">No review items available.</td></tr>'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the hybrid trainer review session web app")
    parser.add_argument("--session", default="", help="review session JSON path or bootstrap file for SQLite/PostgreSQL store")
    parser.add_argument(
        "--auth-token",
        default="",
        help="legacy shared bearer token used when no identity provider config is supplied",
    )
    parser.add_argument("--audit-log", default="", help="audit log JSONL path for file store mode")
    parser.add_argument("--sqlite-db", default="", help="optional SQLite database path for persisted review storage")
    parser.add_argument("--postgres-dsn", default="", help="optional PostgreSQL DSN for persisted review storage")
    parser.add_argument("--session-id", default="", help="session id to load from SQLite/PostgreSQL store")
    parser.add_argument(
        "--identity-provider-config",
        default="",
        help="optional identity provider JSON config for static or OIDC introspection modes",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8000, help="bind port")
    return parser


def build_store_from_args(ns: argparse.Namespace) -> ReviewStore:
    if ns.postgres_dsn:
        return build_review_store(
            postgres_dsn=ns.postgres_dsn,
            session_id=ns.session_id,
            bootstrap_session_path=ns.session,
        )
    if ns.sqlite_db:
        return build_review_store(
            sqlite_db_path=ns.sqlite_db,
            session_id=ns.session_id,
            bootstrap_session_path=ns.session,
        )
    return build_review_store(
        session_path=ns.session,
        audit_log_path=ns.audit_log,
    )


def build_identity_provider_from_args(ns: argparse.Namespace) -> IdentityProvider | None:
    if ns.identity_provider_config:
        return build_identity_provider_from_file(ns.identity_provider_config)
    return None


def main(args: list[str] | None = None) -> None:
    parser = build_parser()
    ns = parser.parse_args(args=args)
    if not ns.identity_provider_config and not ns.auth_token:
        parser.error("--auth-token is required unless --identity-provider-config is set")
    serve_review_server(
        auth_token=ns.auth_token,
        host=ns.host,
        port=ns.port,
        store=build_store_from_args(ns),
        identity_provider=build_identity_provider_from_args(ns),
    )


if __name__ == "__main__":
    main()
