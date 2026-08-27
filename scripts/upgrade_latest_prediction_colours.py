#!/usr/bin/env python3
"""Safely add fixed Mark Six colour metadata to an existing prediction cache.

This is a schema/display migration only.  It does not fetch results, recompute
recommendations, reorder sets, or write append-only prediction, blind-test,
Brier, and weight ledgers.  Existing operational fields stay intact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ball_colours import colour_for_number
from colour_analysis import colour_analysis_payload, recommendation_colour_metadata
from updater import DEFAULT_HISTORY_PATH, DEFAULT_PREDICTION_PATH, load_history


BALL_COLOUR_RESEARCH_NOTE = "固定紅藍綠號碼標籤，只作描述性分析，不加入正式機率、盲測或權重治理。"


def upgrade_latest_prediction_colours(history_path: Path, output_path: Path) -> tuple[dict[str, Any], bool]:
    """Add display-only colour metadata while preserving every existing field."""
    if not output_path.exists():
        raise FileNotFoundError(f"找不到最新研究輸出：{output_path}")
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("最新研究輸出必須為 JSON 物件。")
    history = load_history(history_path)
    updated = dict(payload)

    recommendations = payload.get("top_5_recommendations")
    if isinstance(recommendations, list):
        enriched: list[Any] = []
        for item in recommendations:
            if not isinstance(item, dict):
                enriched.append(item)
                continue
            row = dict(item)
            try:
                numbers = [int(number) for number in row.get("numbers", [])]
                special = row.get("special_number")
                special_number = int(special) if special is not None else None
                if len(numbers) == 6 and len(set(numbers)) == 6 and all(1 <= number <= 49 for number in numbers):
                    row.update(recommendation_colour_metadata(numbers, special_number))
            except (TypeError, ValueError):
                pass
            enriched.append(row)
        updated["top_5_recommendations"] = enriched

    top_weights = payload.get("top_weights")
    if isinstance(top_weights, list):
        enriched_weights: list[Any] = []
        for item in top_weights:
            if not isinstance(item, dict):
                enriched_weights.append(item)
                continue
            row = dict(item)
            try:
                row["ball_colour"] = colour_for_number(int(row.get("number")))
            except (TypeError, ValueError):
                pass
            enriched_weights.append(row)
        updated["top_weights"] = enriched_weights

    model = payload.get("model")
    if isinstance(model, dict):
        model_copy = dict(model)
        context = dict(model_copy.get("research_context", {})) if isinstance(model_copy.get("research_context"), dict) else {}
        context["ball_colours"] = BALL_COLOUR_RESEARCH_NOTE
        model_copy["research_context"] = context
        updated["model"] = model_copy

    updated["colour_analysis"] = colour_analysis_payload(history)
    changed = updated != payload
    if changed:
        output_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated, changed


def main() -> None:
    parser = argparse.ArgumentParser(description="為既有 latest_prediction.json 安全補入固定球色展示資料。")
    parser.add_argument("--history-csv", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_PREDICTION_PATH)
    args = parser.parse_args()
    _payload, changed = upgrade_latest_prediction_colours(args.history_csv, args.output_json)
    print("已補入固定球色展示資料。" if changed else "球色展示資料已是最新；未改動輸出。")


if __name__ == "__main__":
    main()
