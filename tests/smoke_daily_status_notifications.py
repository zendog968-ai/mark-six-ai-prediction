"""No-network smoke checks for the daily Mark Six status summary."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smtp_notifications import dispatch_daily_status, render_daily_status_body


def run() -> None:
    snapshot = {
        "report_date_hkt": "2026-08-23",
        "generated_at_hkt": "2026-08-23T10:00:00+08:00",
        "latest_official_draw": {"draw": "26091", "date": "2026-08-20", "numbers": [1, 2, 3, 4, 5, 6]},
        "latest_blind": {"target_draw": 26092, "status": "locked_pending_result", "variants": []},
        "latest_brier": {"target_draw": 26092, "status": "locked_pending_result"},
        "weight_version": None,
        "common_brier_draws": 0,
        "formal_gate": "等待 100 期",
    }
    assert "受控模擬通知" in render_daily_status_body(snapshot, simulation=True)
    with tempfile.TemporaryDirectory() as temporary:
        ledger = Path(temporary) / "events.json"
        sent: list[str] = []
        settings = {"host": "example", "port": 465, "username": "a", "password": "b", "sender": "a", "recipient": "b"}

        def fake_send(_settings: dict, subject: str, _body: str) -> None:
            sent.append(subject)

        first = dispatch_daily_status(settings, ledger_path=ledger, snapshot=snapshot, send_func=fake_send)
        second = dispatch_daily_status(settings, ledger_path=ledger, snapshot=snapshot, send_func=fake_send)
        assert first["sent"] == 1 and second["skipped"] == 1 and len(sent) == 1
        assert json.loads(ledger.read_text(encoding="utf-8"))["events"][0]["status"] == "sent"


if __name__ == "__main__":
    run()
    print("Daily status notification smoke checks passed.")
