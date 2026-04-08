import json

from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.human_review import load_review_decisions
from hybrid_trainer.pipeline import Decision, DecisionNode


def test_export_review_batch_and_load_review_decisions(tmp_path) -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 4, DecisionNode.FAILURE_REVIEW)

    batch_path = tmp_path / "review_batch.json"
    engine.export_review_batch(str(batch_path), budget=2)

    payload = json.loads(batch_path.read_text(encoding="utf-8"))
    assert payload["budget"] == 2
    assert len(payload["items"]) == 2

    decisions_path = tmp_path / "review_decisions.json"
    decisions_path.write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "iteration": payload["items"][0]["iteration"],
                        "final_decision": Decision.APPROVE.value,
                        "reviewer": "alice",
                        "note": "accepted after review",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    decisions = load_review_decisions(str(decisions_path))
    assert decisions[0].reviewer == "alice"
    assert decisions[0].final_decision == Decision.APPROVE
