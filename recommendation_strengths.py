"""Read-only recommendation-strength helpers for research presentation.

These values are relative model scores, not calibrated win probabilities and
must never be interpreted as an advantage over a fair random draw.
"""

from __future__ import annotations

from typing import Any


def recommendation_strengths(recommendations: Any, number_weights: Any) -> list[dict[str, Any]]:
    """Copy and annotate recommendation groups with relative mean-score strength.

    The strongest valid six-main-number group receives 100.  Remaining groups
    are expressed relative to it.  Invalid or incomplete groups retain a clear
    unavailable label rather than an invented score.
    """
    weights: dict[int, float] = {}
    if isinstance(number_weights, dict):
        raw_items = number_weights.items()
    elif isinstance(number_weights, list):
        raw_items = ((item.get("number"), item.get("relative_weight")) for item in number_weights if isinstance(item, dict))
    else:
        raw_items = []
    for number, weight in raw_items:
        try:
            parsed_number = int(number)
            parsed_weight = float(weight)
        except (TypeError, ValueError):
            continue
        if 1 <= parsed_number <= 49 and parsed_weight >= 0:
            weights[parsed_number] = parsed_weight

    annotated: list[dict[str, Any]] = []
    raw_scores: list[float | None] = []
    for item in recommendations if isinstance(recommendations, list) else []:
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        try:
            numbers = [int(number) for number in copied.get("numbers", [])]
        except (TypeError, ValueError):
            numbers = []
        if len(numbers) == 6 and len(set(numbers)) == 6 and all(number in weights for number in numbers):
            score = sum(weights[number] for number in numbers) / 6
        else:
            score = None
        annotated.append(copied)
        raw_scores.append(score)

    strongest = max((score for score in raw_scores if score is not None), default=None)
    for item, score in zip(annotated, raw_scores):
        if score is None or strongest is None or strongest <= 0:
            item["relative_strength_percent"] = None
            item["strength_label"] = "相對推薦強度未提供"
            continue
        percent = int(round((score / strongest) * 100))
        item["strength_score"] = round(score, 6)
        item["relative_strength_percent"] = percent
        item["strength_label"] = f"相對推薦強度 {percent}%"
    return annotated


def sort_recommendations_by_strength(recommendations: list[list[int]], number_weights: dict[int, float]) -> list[list[int]]:
    """Sort valid six-number groups descending by mean fusion score, deterministically."""
    def score(numbers: list[int]) -> tuple[float, tuple[int, ...]]:
        mean = sum(float(number_weights.get(number, 0.0)) for number in numbers) / max(len(numbers), 1)
        return (-mean, tuple(numbers))

    return sorted((list(group) for group in recommendations), key=score)
