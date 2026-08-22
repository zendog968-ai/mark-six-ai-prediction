"""Rebuild the next Mark Six prediction without network access or data writes.

This script deliberately uses the latest row already stored in the verified CSV.
It is intended for audit checks of an already locked target draw and must not be
used to overwrite latest_prediction.json, blind-test records, or history CSVs.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from updater import DrawResult, build_prediction_payload, load_history


HISTORY_PATH = PROJECT_ROOT / "data" / "lotto_history_real.csv"
LOCKED_OUTPUT_PATH = PROJECT_ROOT / "data" / "latest_prediction.json"
REPORT_PATH = PROJECT_ROOT / "data" / "runtime_prediction_verification.json"


def latest_draw_from_history() -> DrawResult:
    history = load_history(HISTORY_PATH)
    row = history.iloc[-1]
    return DrawResult(
        draw=int(row["Draw"]),
        date=str(row["Date"]),
        main_numbers=tuple(int(row[f"N{index}"]) for index in range(1, 7)),
        special=int(row["Special"]),
        source_url="verified_local_history",
    )


def main() -> None:
    history = load_history(HISTORY_PATH)
    latest = latest_draw_from_history()
    rebuilt = build_prediction_payload(history, latest, appended=False)
    locked = json.loads(LOCKED_OUTPUT_PATH.read_text(encoding="utf-8"))
    target_draw = int(latest.draw) + 1
    report = {
        "mode": "read_only_local_rebuild",
        "latest_verified_draw": asdict(latest),
        "target_draw": target_draw,
        "history_records": len(history),
        "top_weights_match_locked": rebuilt["top_weights"] == locked.get("top_weights"),
        "recommendations_match_locked": rebuilt["top_5_recommendations"] == locked.get("top_5_recommendations"),
        "rebuilt_top_weights": rebuilt["top_weights"][:10],
        "rebuilt_recommendations": rebuilt["top_5_recommendations"],
        "notice": "驗證輸出不會寫入歷史 CSV、latest_prediction.json、盲測或權重記錄。",
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
