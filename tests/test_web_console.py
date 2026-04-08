from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.web_console import render_decision_console_html, save_decision_console_html


def test_render_decision_console_html_contains_sections(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 4, DecisionNode.FAILURE_REVIEW)
    console = engine.generate_decision_console(review_budget=2, active_learning_limit=2, recent_event_limit=3)

    html = render_decision_console_html(console)

    assert "<title>Hybrid Trainer Visual Console</title>" in html
    assert "Major Node Recommendations" in html
    assert "Prioritized Review Queue" in html

    output = save_decision_console_html(console, str(tmp_path / "console.html"))
    saved = output.read_text(encoding="utf-8")
    assert "Visual Decision Console" in saved
