"""Standard-library smoke checks for SMTP event selection and idempotency."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smtp_notifications import collect_weight_events, dispatch_events
from weight_monitor import CONFIG_LABELS


def weights() -> dict[str, float]:
    return {key: 0.25 for key in CONFIG_LABELS}


def run() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        history = root / "weights.json"
        ledger = root / "events.json"
        history.write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "version": "weights-v1",
                            "status": "frozen",
                            "locked_at": "2026-08-22T00:00:00+00:00",
                            "formal_qualification_passed": True,
                            "freeze_completed_draws": 25,
                            "proposed_weights": weights(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        events = collect_weight_events(json.loads(history.read_text(encoding="utf-8"))["records"])
        assert {event["event_type"] for event in events} == {"freeze_started", "freeze_25_draws"}
        sent: list[str] = []

        def fake_send(_settings: dict, subject: str, _body: str) -> None:
            sent.append(subject)

        settings = {"host": "example", "port": 465, "username": "a", "password": "b", "sender": "a", "recipient": "b"}
        first = dispatch_events(settings, weight_history_path=history, ledger_path=ledger, send_func=fake_send)
        second = dispatch_events(settings, weight_history_path=history, ledger_path=ledger, send_func=fake_send)
        assert first["sent"] == 2 and second["sent"] == 0 and second["skipped"] == 2
        assert len(sent) == 2


if __name__ == "__main__":
    run()
    print("SMTP notification smoke checks passed.")
