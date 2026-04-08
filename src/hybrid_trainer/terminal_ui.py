from __future__ import annotations

from .decision_console import DecisionConsole
from .human_review import HumanReviewDecision
from .review_router import RoutedReviewBatch
from .pipeline import Decision


def render_decision_console(console: DecisionConsole) -> str:
    data = console.to_dict()
    lines = [
        "Hybrid Trainer Decision Console",
        f"Metrics: total={data['dashboard']['metrics']['total']} approve={data['dashboard']['metrics']['approve']} "
        f"review={data['dashboard']['metrics']['review']} block={data['dashboard']['metrics']['block']}",
        f"Review Queue: pending={data['review_queue']['pending_count']} resolved={data['review_queue']['resolved_count']} "
        f"budget={data['review_queue']['budget']}",
        f"Review Consensus: total={data['review_consensus']['total_groups']} "
        f"consensus={data['review_consensus']['consensus_groups']} "
        f"arbitrated={data['review_consensus']['arbitrated_groups']}",
        f"Strategy: current={data['strategy']['current']} recommended={data['strategy']['recommended']}",
        f"Curriculum: current={data['curriculum']['current_stage']} next={data['curriculum']['next_stage'] or '-'}",
        f"Policy: active={data['policy']['active_version'] or '-'}",
    ]

    if data["major_node_recommendations"]:
        lines.append("Major Node Recommendations:")
        lines.extend(
            f"- {item['node']}: {item['reason']}"
            for item in data["major_node_recommendations"]
        )

    if data["review_queue"]["prioritized_items"]:
        lines.append("Prioritized Review Items:")
        lines.extend(
            f"- iter={item['iteration']} node={item['node']} score={item['auto_score']:.2f} "
            f"decision={item['auto_decision']} risk={item['risk_score']:.2f}"
            for item in data["review_queue"]["prioritized_items"]
        )

    if data["active_learning"]["candidates"]:
        lines.append("Active Learning Candidates:")
        lines.extend(
            f"- iter={item['iteration']} score={item['score']:.2f} uncertainty={item['uncertainty']:.2f}"
            for item in data["active_learning"]["candidates"]
        )

    if data["recent_events"]:
        lines.append("Recent Events:")
        lines.extend(
            f"- {item['timestamp']} {item['event_type']}"
            for item in data["recent_events"]
        )

    return "\n".join(lines) + "\n"


def render_review_batch(batch: RoutedReviewBatch) -> str:
    lines = [
        f"Human Review Batch (budget={batch.budget}, selected={len(batch.items)})",
    ]
    if not batch.items:
        lines.append("No pending review items.")
    else:
        lines.extend(
            f"- iter={item.iteration} node={item.node.value} score={item.auto_score:.2f} auto={item.auto_decision.value}"
            for item in batch.items
        )
        lines.append("Decision template:")
        lines.append('{"decisions": [{"iteration": 1, "final_decision": "approve", "reviewer": "alice", "note": ""}]}')
    return "\n".join(lines) + "\n"


def collect_review_decisions(
    batch: RoutedReviewBatch,
    reviewer: str,
    input_fn=None,
) -> list[HumanReviewDecision]:
    input_fn = input_fn or input
    decisions: list[HumanReviewDecision] = []
    for item in batch.items:
        decision = _prompt_decision(item.iteration, item.node.value, item.auto_score, item.auto_decision.value, input_fn)
        if decision is None:
            continue
        note = input_fn(f"note for iteration {item.iteration}: ").strip()
        decisions.append(
            HumanReviewDecision(
                iteration=item.iteration,
                final_decision=decision,
                reviewer=reviewer,
                note=note,
            )
        )
    return decisions


def _prompt_decision(
    iteration: int,
    node: str,
    auto_score: float,
    auto_decision: str,
    input_fn=None,
) -> Decision | None:
    input_fn = input_fn or input
    prompt = (
        f"iteration {iteration} [{node}] score={auto_score:.2f} auto={auto_decision} "
        "decision (approve/review/block/skip): "
    )
    while True:
        raw = input_fn(prompt).strip().lower()
        if raw in {"", "skip"}:
            return None
        if raw in {item.value for item in Decision}:
            return Decision(raw)
