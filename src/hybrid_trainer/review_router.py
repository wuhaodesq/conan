from __future__ import annotations

from dataclasses import dataclass

from .human_review import HumanReviewItem
from .pipeline import Decision


@dataclass(slots=True)
class RoutedReviewBatch:
    items: list[HumanReviewItem]
    budget: int


def _risk_score(item: HumanReviewItem) -> float:
    # Higher means should be reviewed earlier.
    base = 1.0 - item.auto_score
    if item.auto_decision == Decision.BLOCK:
        base += 0.2
    return base


def route_review_items(pending: list[HumanReviewItem], budget: int) -> RoutedReviewBatch:
    if budget <= 0:
        return RoutedReviewBatch(items=[], budget=budget)

    ranked = sorted(pending, key=_risk_score, reverse=True)
    return RoutedReviewBatch(items=ranked[:budget], budget=budget)
