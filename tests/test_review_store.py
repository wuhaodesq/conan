import json
from io import BytesIO
import threading
from types import SimpleNamespace
from urllib.request import Request, urlopen

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.human_review import HumanReviewDecision
from hybrid_trainer.pipeline import Decision, DecisionNode
from hybrid_trainer.review_audit import create_review_audit_event
from hybrid_trainer.review_router import route_review_items
from hybrid_trainer.review_server import build_review_server
from hybrid_trainer.review_permissions import ReviewPermissionPolicy
from hybrid_trainer.review_session import ReviewSession, save_review_session
from hybrid_trainer.review_store import ObjectStorageReviewStore, PostgresReviewStore, SqliteReviewStore, build_review_store


class _FakePgState:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, str]] = {}
        self.audit_events: list[dict[str, str]] = []


class _FakePgConnection:
    def __init__(self, state: _FakePgState) -> None:
        self.state = state

    async def execute(self, statement: str, *args) -> str:
        normalized = " ".join(statement.split())
        if normalized.startswith("CREATE TABLE") or normalized.startswith("CREATE INDEX"):
            return "CREATE"
        if "INSERT INTO review_sessions" in normalized:
            session_id, payload, updated_at = args
            self.state.sessions[str(session_id)] = {
                "payload": str(payload),
                "updated_at": str(updated_at),
            }
            return "INSERT 0 1"
        if "INSERT INTO review_audit_events" in normalized:
            session_id, timestamp, action, actor, role, payload = args
            self.state.audit_events.append(
                {
                    "session_id": str(session_id),
                    "timestamp": str(timestamp),
                    "action": str(action),
                    "actor": str(actor),
                    "role": str(role),
                    "payload": str(payload),
                }
            )
            return "INSERT 0 1"
        raise AssertionError(f"unexpected SQL statement: {statement}")

    async def fetchrow(self, statement: str, *args):
        if "SELECT payload FROM review_sessions" not in statement:
            raise AssertionError(f"unexpected fetchrow statement: {statement}")
        entry = self.state.sessions.get(str(args[0]))
        if entry is None:
            return None
        return (entry["payload"],)

    async def fetch(self, statement: str, *args):
        if "FROM review_audit_events" not in statement:
            raise AssertionError(f"unexpected fetch statement: {statement}")
        session_id = str(args[0])
        return [
            (
                item["action"],
                item["actor"],
                item["role"],
                item["session_id"],
                item["payload"],
                item["timestamp"],
            )
            for item in self.state.audit_events
            if item["session_id"] == session_id
        ]

    async def close(self) -> None:
        return None


class _FakeObjectStorageClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def get_object(self, *, Bucket: str, Key: str):
        payload = self.objects.get((Bucket, Key))
        if payload is None:
            raise FileNotFoundError(f"missing object: {Bucket}/{Key}")
        return {"Body": BytesIO(payload)}

    def put_object(self, *, Bucket: str, Key: str, Body, ContentType: str):
        if isinstance(Body, bytes):
            payload = Body
        elif hasattr(Body, "read"):
            payload = Body.read()
        else:
            payload = str(Body).encode("utf-8")
        self.objects[(Bucket, Key)] = payload
        return {"ETag": "fake"}


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


def test_postgres_review_store_persists_sessions_and_audit(monkeypatch, tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
    batch = route_review_items(engine.review_queue.pending, budget=2)
    permission_policy = ReviewPermissionPolicy.from_dict(
        {
            "roles": [
                {
                    "role": "reviewer",
                    "allowed_decisions": ["approve", "review"],
                    "can_resolve": True,
                    "can_export": True,
                },
                {
                    "role": "admin",
                    "allowed_decisions": ["approve", "review", "block"],
                    "can_resolve": True,
                    "can_export": True,
                },
            ]
        }
    )
    session = ReviewSession.create(console=console, batch=batch, permission_policy=permission_policy)
    session_path = tmp_path / "review_session.json"
    save_review_session(session, str(session_path))

    state = _FakePgState()

    async def fake_connect(*, dsn: str, timeout: int):
        assert dsn == "postgresql://localhost/hybrid"
        assert timeout == 5
        return _FakePgConnection(state)

    monkeypatch.setattr("hybrid_trainer.review_store.asyncpg.connect", fake_connect)

    store = build_review_store(
        postgres_dsn="postgresql://localhost/hybrid",
        bootstrap_session_path=str(session_path),
    )
    assert isinstance(store, PostgresReviewStore)

    loaded_session = store.load_session()
    first_iteration = loaded_session.review_batch["items"][0]["iteration"]
    loaded_session.sync_reviewer_submission(
        reviewer="alice",
        role="reviewer",
        decisions=[
            HumanReviewDecision(
                iteration=first_iteration,
                final_decision=Decision.APPROVE,
                reviewer="alice",
                note="approved from postgres store",
            )
        ],
    )
    store.save_session(loaded_session)
    store.append_audit_event(
        create_review_audit_event(
            action="decisions_submitted",
            actor="alice",
            role="reviewer",
            session_id=loaded_session.session_id,
            payload={"decision_count": 1},
        )
    )

    persisted_store = PostgresReviewStore(
        database_url="postgresql://localhost/hybrid",
        session_id=loaded_session.session_id,
    )
    persisted_session = persisted_store.load_session()
    assert persisted_session.summary()["submitted_decisions"] == 1
    assert persisted_store.load_audit_events()[0].actor == "alice"


def test_object_storage_review_store_persists_sessions_and_audit(monkeypatch, tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
    batch = route_review_items(engine.review_queue.pending, budget=2)
    session = ReviewSession.create(console=console, batch=batch)
    session_path = tmp_path / "review_session.json"
    save_review_session(session, str(session_path))

    client = _FakeObjectStorageClient()
    monkeypatch.setattr(
        "hybrid_trainer.review_store.boto3",
        SimpleNamespace(client=lambda service_name, **kwargs: client),
    )

    store = build_review_store(
        object_store_bucket="hybrid-review",
        object_store_prefix="training",
        bootstrap_session_path=str(session_path),
    )
    assert isinstance(store, ObjectStorageReviewStore)

    loaded_session = store.load_session()
    first_iteration = loaded_session.review_batch["items"][0]["iteration"]
    loaded_session.sync_reviewer_submission(
        reviewer="alice",
        role="reviewer",
        decisions=[
            HumanReviewDecision(
                iteration=first_iteration,
                final_decision=Decision.APPROVE,
                reviewer="alice",
                note="approved from object storage",
            )
        ],
    )
    store.save_session(loaded_session)
    store.append_audit_event(
        create_review_audit_event(
            action="decisions_submitted",
            actor="alice",
            role="reviewer",
            session_id=loaded_session.session_id,
            payload={"decision_count": 1},
        )
    )

    persisted_store = ObjectStorageReviewStore(
        bucket_name="hybrid-review",
        object_prefix="training",
        session_id=loaded_session.session_id,
    )
    persisted_store.client = client
    persisted_session = persisted_store.load_session()
    assert persisted_session.summary()["submitted_decisions"] == 1
    assert persisted_store.load_audit_events()[0].actor == "alice"
