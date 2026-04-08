import json

from hybrid_trainer.cli import run
from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.review_permissions import ReviewPermissionPolicy
from hybrid_trainer.review_router import route_review_items
from hybrid_trainer.review_web import render_review_workbench_html, save_review_workbench_html


def test_render_review_workbench_html_contains_export_flow(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)
    batch = route_review_items(engine.review_queue.pending, budget=2)

    html = render_review_workbench_html(console, batch, reviewer="alice", role="reviewer")

    assert "<title>Hybrid Trainer Review Workbench</title>" in html
    assert "Download review_decisions.json" in html
    assert "alice" in html

    output = save_review_workbench_html(console, batch, str(tmp_path / "review.html"), reviewer="alice")
    assert "Web Review Workbench" in output.read_text(encoding="utf-8")


def test_viewer_role_is_read_only_in_review_workbench() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 2, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=1, active_learning_limit=1, recent_event_limit=1)
    batch = route_review_items(engine.review_queue.pending, budget=1)

    html = render_review_workbench_html(console, batch, reviewer="observer", role="viewer")

    assert "Read-only session" in html
    assert 'disabled aria-disabled="true"' in html


def test_cli_can_export_review_workbench_with_custom_permissions(tmp_path) -> None:
    summary = tmp_path / "summary.json"
    review_web = tmp_path / "review.html"
    permissions = tmp_path / "permissions.json"
    permissions.write_text(
        json.dumps(
            {
                "roles": [
                    {
                        "role": "triager",
                        "allowed_decisions": ["approve", "review"],
                        "can_resolve": True,
                        "can_export": True,
                        "description": "Can triage without issuing hard blocks.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    run([
        "--start",
        "1",
        "--end",
        "3",
        "--node",
        "failure_review",
        "--review-budget",
        "2",
        "--review-web-output",
        str(review_web),
        "--reviewer",
        "web_alice",
        "--review-role",
        "triager",
        "--review-permissions-config",
        str(permissions),
        "--output",
        str(summary),
    ])

    summary_data = json.loads(summary.read_text(encoding="utf-8"))
    html = review_web.read_text(encoding="utf-8")

    assert summary_data["inputs"]["review_role"] == "triager"
    assert summary_data["inputs"]["review_permissions_config"] == str(permissions)
    assert "web_alice" in html
    assert "Can triage without issuing hard blocks." in html
    assert 'value="approve"' in html
    assert 'value="review"' in html
    assert 'value="block"' not in html


def test_review_permission_policy_default_roles_include_reviewer_and_viewer() -> None:
    policy = ReviewPermissionPolicy.default()

    assert policy.resolve("reviewer").can_export is True
    assert policy.resolve("viewer").can_resolve is False
