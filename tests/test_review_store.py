import json
import threading
from urllib.request import Request, urlopen

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.review_router import route_review_items
from hybrid_trainer.review_server import build_review_server
from hybrid_trainer.review_session import ReviewSession, save_review_session
from hybrid_trainer.review_store import SqliteReviewStore, build_review_store


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


def test_sqlite_review_store_persists_sessions_and_audit(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
    batch = route_review_items(engine.review_queue.pending, budget=2)
    session = ReviewSession.create(console=console, batch=batch)

    session_path = tmp_path / "review_session.json"
    database_path = tmp_path / "review.sqlite"
    save_review_session(session, str(session_path))

    store = build_review_store(
        sqlite_db_path=str(database_path),
        bootstrap_session_path=str(session_path),
    )
    assert isinstance(store, SqliteReviewStore)

    server = build_review_server(auth_token="secret-token", store=store, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        session_payload = _request_json(f"{base_url}/api/session", token="secret-token")
        assert session_payload["summary"]["session_id"] == session.session_id

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
                        "note": "approved from sqlite store",
                    }
                ],
            },
        )
        assert submit_payload["summary"]["submitted_decisions"] == 1

        audit_payload = _request_json(f"{base_url}/api/audit?role=admin", token="secret-token")
        assert audit_payload["events"][0]["action"] == "decisions_submitted"
        assert audit_payload["events"][0]["actor"] == "alice"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    persisted_store = SqliteReviewStore(database_path=str(database_path), session_id=session.session_id)
    assert persisted_store.load_session().summary()["submitted_decisions"] == 1
    assert persisted_store.load_audit_events()[0].actor == "alice"
