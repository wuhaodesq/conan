from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
from typing import Any
from urllib.parse import parse_qs, urlparse

from .human_review import HumanReviewDecision
from .review_audit import append_review_audit_event, create_review_audit_event, load_review_audit_events
from .review_session import ReviewSession, load_review_session, save_review_session


def build_review_server(
    session_path: str,
    auth_token: str,
    audit_log_path: str,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    app = ReviewServerApp(
        session_path=session_path,
        auth_token=auth_token,
        audit_log_path=audit_log_path,
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
    session_path: str,
    auth_token: str,
    audit_log_path: str,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    server = build_review_server(
        session_path=session_path,
        auth_token=auth_token,
        audit_log_path=audit_log_path,
        host=host,
        port=port,
    )
    with server:
        server.serve_forever()


class ReviewServerApp:
    def __init__(self, session_path: str, auth_token: str, audit_log_path: str) -> None:
        self.session_path = session_path
        self.auth_token = auth_token
        self.audit_log_path = audit_log_path
        self._lock = threading.Lock()

    def handle(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if not self._authenticate(handler, parsed):
            self._send_json(handler, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        if handler.command == "GET" and parsed.path == "/":
            self._send_html(handler, self._render_index(parsed))
            return
        if handler.command == "GET" and parsed.path == "/api/session":
            session = load_review_session(self.session_path)
            self._send_json(handler, HTTPStatus.OK, session.to_dict())
            return
        if handler.command == "GET" and parsed.path == "/api/audit":
            role = _query_value(parsed, "role", "viewer")
            if role != "admin":
                self._send_json(handler, HTTPStatus.FORBIDDEN, {"error": "admin role required"})
                return
            events = [item.to_dict() for item in load_review_audit_events(self.audit_log_path)]
            self._send_json(handler, HTTPStatus.OK, {"events": events})
            return
        if handler.command == "POST" and parsed.path == "/api/decisions":
            payload = self._read_json(handler)
            reviewer = str(payload["reviewer"])
            role = str(payload["role"])
            decisions = [HumanReviewDecision.from_dict(item) for item in payload.get("decisions", [])]
            with self._lock:
                session = load_review_session(self.session_path)
                session.sync_reviewer_submission(reviewer=reviewer, role=role, decisions=decisions)
                save_review_session(session, self.session_path)
                append_review_audit_event(
                    self.audit_log_path,
                    create_review_audit_event(
                        action="decisions_submitted",
                        actor=reviewer,
                        role=role,
                        session_id=session.session_id,
                        payload={
                            "decision_count": len(decisions),
                            "iterations": [item.iteration for item in decisions],
                        },
                    ),
                )
            self._send_json(
                handler,
                HTTPStatus.OK,
                {
                    "session": session.to_dict(),
                    "summary": session.summary(),
                },
            )
            return

        self._send_json(handler, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _authenticate(self, handler: BaseHTTPRequestHandler, parsed) -> bool:
        header = handler.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[len("Bearer "):]
        else:
            token = _query_value(parsed, "token", "")
        return bool(token) and secrets.compare_digest(token, self.auth_token)

    def _read_json(self, handler: BaseHTTPRequestHandler) -> dict:
        length = int(handler.headers.get("Content-Length", "0"))
        raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _render_index(self, parsed) -> str:
        reviewer = _query_value(parsed, "reviewer", "web_reviewer")
        role = _query_value(parsed, "role", "reviewer")
        token = _query_value(parsed, "token", "")
        session = load_review_session(self.session_path)
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
      <p>Use the same Bearer token for the API endpoints below. Submitted decisions are persisted to the review session file and appended to the audit log.</p>
    </section>
    <section class="panel">
      <h2>Session API</h2>
      <pre id="session-json">loading...</pre>
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
    const authToken = {json.dumps(token)};
    const reviewer = {json.dumps(reviewer)};
    const role = {json.dumps(role)};

    async function loadSession() {{
      const response = await fetch('/api/session', {{
        headers: {{ Authorization: `Bearer ${{authToken}}` }}
      }});
      const payload = await response.json();
      document.getElementById('session-json').textContent = JSON.stringify(payload.summary || payload, null, 2);
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
    }}

    document.getElementById('submit').addEventListener('click', submitDecisions);
    loadSession();
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
    parser.add_argument("--session", required=True, help="review session JSON path")
    parser.add_argument("--auth-token", required=True, help="Bearer token used for all review server requests")
    parser.add_argument("--audit-log", required=True, help="audit log JSONL path")
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8000, help="bind port")
    return parser


def main(args: list[str] | None = None) -> None:
    parser = build_parser()
    ns = parser.parse_args(args=args)
    serve_review_server(
        session_path=ns.session,
        auth_token=ns.auth_token,
        audit_log_path=ns.audit_log,
        host=ns.host,
        port=ns.port,
    )


if __name__ == "__main__":
    main()
