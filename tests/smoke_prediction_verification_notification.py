"""No-network smoke check for controlled prediction verification email content."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smtp_notifications import render_prediction_verification_body


def run() -> None:
    report = {
        "target_draw": 26092,
        "latest_verified_draw": {"draw": 26091},
        "history_records": 225,
        "top_weights_match_locked": True,
        "recommendations_match_locked": True,
        "rebuilt_top_weights": [{"number": 7, "relative_weight": 0.679232}],
        "rebuilt_recommendations": [{"set_index": 1, "numbers": [1, 18, 30, 31, 45, 48]}],
    }
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        subject, body = render_prediction_verification_body(path)
        assert "26092" in subject and "受控預測重建" in body and "01、18、30、31、45、48" in body


if __name__ == "__main__":
    run()
    print("Prediction verification notification smoke check passed.")
