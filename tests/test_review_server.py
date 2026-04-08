import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.review_router import route_review_items
from hybrid_trainer.review_server import build_parser, build_review_server, build_store_from_args
from hybrid_trainer.review_session import ReviewSession, load_review_session, save_review_session


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


def test_review_server_requires_auth_and_persists_audit_log(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
    batch = route_review_items(engine.review_queue.pending, budget=2)
    session_path = tmp_path / "review_session.json"
    audit_log = tmp_path / "audit.jsonl"
    save_review_session(ReviewSession.create(console=console, batch=batch), str(session_path))

    server = build_review_server(
        session_path=str(session_path),
        auth_token="secret-token",
        audit_log_path=str(audit_log),
        host="127.0.0.1",
        port=0,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"

        try:
            _request_json(f"{base_url}/api/session")
            assert False, "expected unauthorized request to fail"
        except HTTPError as exc:
            assert exc.code == 401

        with urlopen(  # noqa: S310
            Request(
                f"{base_url}/?reviewer=alice&role=reviewer",
                headers={"Authorization": "Bearer secret-token"},
            ),
            timeout=5,
        ) as response:
            html = response.read().decode("utf-8")
        assert "Review Server Workbench" in html

        session_payload = _request_json(f"{base_url}/api/session", token="secret-token")
        assert session_payload["summary"]["session_id"].startswith("review-session-")

        first_iteration = session_payload["review_batch"]["items"][0]["iteration"]
        submit_payload = _request_json(
            f"{base_url}/api/decisions",
            token="secret-token",
            method="POST",
            payload={
                "reviewer": "alice",
                "role": "reviewer",
                "decisions": [
                    {
                        "iteration": first_iteration,
                        "final_decision": "approve",
                        "reviewer": "alice",
                        "note": "approved from server",
                    }
                ],
            },
        )
        assert submit_payload["summary"]["submitted_decisions"] == 1

        audit_payload = _request_json(f"{base_url}/api/audit?role=admin", token="secret-token")
        assert audit_payload["events"][0]["action"] == "decisions_submitted"
        assert audit_payload["events"][0]["actor"] == "alice"

        updated_session = load_review_session(str(session_path))
        assert updated_session.summary()["submitted_decisions"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_review_server_parser_routes_postgres_backend(monkeypatch) -> None:
    captured = {}

    def fake_build_review_store(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hybrid_trainer.review_server.build_review_store", fake_build_review_store)

    ns = build_parser().parse_args(
        [
            "--postgres-dsn",
            "postgresql://localhost/hybrid",
            "--session",
            "bootstrap.json",
            "--session-id",
            "session-alpha",
        ]
    )
    store = build_store_from_args(ns)

    assert store is not None
    assert captured["postgres_dsn"] == "postgresql://localhost/hybrid"
    assert captured["session_id"] == "session-alpha"
    assert captured["bootstrap_session_path"] == "bootstrap.json"


def test_review_server_parser_routes_object_store_backend(monkeypatch) -> None:
    captured = {}

    def fake_build_review_store(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hybrid_trainer.review_server.build_review_store", fake_build_review_store)

    ns = build_parser().parse_args(
        [
            "--object-store-bucket",
            "hybrid-review",
            "--object-store-prefix",
            "training",
            "--object-store-endpoint-url",
            "http://localhost:9000",
            "--object-store-region-name",
            "us-east-1",
            "--object-store-no-ssl",
            "--object-store-force-path-style",
            "--object-store-timeout-seconds",
            "7",
            "--session",
            "bootstrap.json",
            "--session-id",
            "session-alpha",
        ]
    )
    store = build_store_from_args(ns)

    assert store is not None
    assert captured["object_store_bucket"] == "hybrid-review"
    assert captured["object_store_prefix"] == "training"
    assert captured["object_store_endpoint_url"] == "http://localhost:9000"
    assert captured["object_store_region_name"] == "us-east-1"
    assert captured["object_store_use_ssl"] is False
    assert captured["object_store_force_path_style"] is True
    assert captured["object_store_timeout_seconds"] == 7
    assert captured["session_id"] == "session-alpha"
    assert captured["bootstrap_session_path"] == "bootstrap.json"
