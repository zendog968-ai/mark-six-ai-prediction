#!/usr/bin/env python3
"""Rebuild only ``latest_prediction.json`` from already verified local history.

This maintenance tool deliberately does not fetch public results and does not
touch the append-only prediction, blind-test, Brier, or weight ledgers. It is
intended for schema-format migrations such as the first 6+1 research group.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from updater import DEFAULT_HISTORY_PATH, DEFAULT_PREDICTION_PATH, DrawResult, build_prediction_payload, load_history


LOCAL_HISTORY_SOURCE = "local-history-rebuild"


def latest_draw_from_history(history) -> DrawResult:
    """Create a validated draw-like source record from the final history row."""
    latest = history.iloc[-1]
    return DrawResult(
        draw=int(latest["Draw"]),
        date=latest["Date"].date().isoformat(),
        main_numbers=tuple(int(latest[f"N{index}"]) for index in range(1, 7)),
        special=int(latest["Special"]),
        source_url=LOCAL_HISTORY_SOURCE,
    )


def rebuild_latest_prediction(history_path: Path, output_path: Path) -> dict[str, object]:
    """Write only the current research payload using the current code schema."""
    history = load_history(history_path)
    if history.empty:
        raise RuntimeError("歷史資料不可為空。")
    payload = build_prediction_payload(history, latest_draw_from_history(history), appended=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="由已驗證本機歷史重建 latest_prediction.json 的展示格式。")
    parser.add_argument("--history-csv", type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_PREDICTION_PATH)
    args = parser.parse_args()
    payload = rebuild_latest_prediction(args.history_csv, args.output_json)
    first = payload["top_5_recommendations"][0]
    print(f"已重建研究輸出：第一組 6+1 特別號碼為 {int(first['special_number']):02d}；未改寫任何盲測或預測歷史帳本。")


if __name__ == "__main__":
    main()
