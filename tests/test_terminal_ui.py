from hybrid_trainer.decision_console import DecisionConsole
from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.review_router import route_review_items
from hybrid_trainer.terminal_ui import collect_review_decisions, render_decision_console, render_review_batch


def test_render_decision_console_contains_key_sections() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=2)

    rendered = render_decision_console(console)

    assert "Hybrid Trainer Decision Console" in rendered
    assert "Metrics:" in rendered
    assert "Review Queue:" in rendered


def test_render_review_batch_and_collect_decisions() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 2, DecisionNode.FAILURE_REVIEW)
    batch = route_review_items(engine.review_queue.pending, budget=1)

    rendered = render_review_batch(batch)
    answers = iter(["approve", "manual keep"])
    decisions = collect_review_decisions(batch, reviewer="alice", input_fn=lambda _prompt="": next(answers))

    assert "Human Review Batch" in rendered
    assert decisions[0].reviewer == "alice"
    assert decisions[0].final_decision.value == "approve"
