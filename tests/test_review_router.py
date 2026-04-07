from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.review_router import route_review_items


def test_route_review_items_respects_budget_and_priority() -> None:
    engine = TrainingEngine()
    engine.run_cycle(2, DecisionNode.FAILURE_REVIEW)  # block, score 0.2
    engine.run_cycle(7, DecisionNode.FAILURE_REVIEW)  # review, score 0.7
    engine.run_cycle(1, DecisionNode.FAILURE_REVIEW)  # block, score 0.1

    batch = route_review_items(engine.review_queue.pending, budget=2)
    assert len(batch.items) == 2
    assert batch.items[0].iteration == 1
    assert batch.items[1].iteration == 2


def test_engine_get_review_batch_tracks_event() -> None:
    engine = TrainingEngine()
    engine.run_cycles(1, 3, DecisionNode.FAILURE_REVIEW)
    batch = engine.get_review_batch(budget=1)

    assert len(batch.items) == 1
    assert any(event.event_type == "review_batch_routed" for event in engine.tracker.events)
