"""Backfill browsable reports for legacy daily-summary events without sending mail.

The pre-archive system stored event IDs and submission timestamps but not the
rendered message. This script reconstructs an explicitly labelled report from
the repository revision available at or before each already-sent event. It
never invokes SMTP, result collection, or formal-ledger writers.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from daily_report_archive import (  # noqa: E402
    DEFAULT_DAILY_REPORT_ARCHIVE_PATH,
    append_reconstructed_daily_report,
)
from smtp_notifications import (  # noqa: E402
    DEFAULT_EVENT_LEDGER_PATH,
    build_daily_status_snapshot,
    render_daily_status_body,
    render_daily_status_html,
)
from weight_monitor import DEFAULT_WEIGHT_HISTORY_PATH  # noqa: E402


HISTORICAL_DATA_FILES = (
    "data/lotto_history_real.csv",
    "data/blind_test_history.json",
    "data/brier_tracking_history.json",
    "data/weight_adjustment_history.json",
    "data/latest_prediction.json",
)
HONG_KONG_TZ = ZoneInfo("Asia/Hong_Kong")


def _git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, text=True, capture_output=True, check=True
    )
    return completed.stdout


def _commit_for_timestamp(timestamp: str) -> str | None:
    commit = _git_text("rev-list", "-1", f"--before={timestamp}", "HEAD").strip()
    return commit or None


def event_timestamp_hkt(timestamp: str) -> tuple[str, str]:
    """Return HKT report date and display timestamp from a UTC ledger event."""
    converted = datetime.fromisoformat(timestamp).astimezone(HONG_KONG_TZ)
    return converted.date().isoformat(), converted.isoformat()


def _sent_daily_events(ledger_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    events = payload.get("events", []) if isinstance(payload, dict) else []
    return [
        event
        for event in events
        if isinstance(event, dict)
        and event.get("event_type") == "daily_summary"
        and event.get("status") == "sent"
        and event.get("sent_at")
    ]


def _snapshot_at_revision(revision: str, event_timestamp: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for relative_path in HISTORICAL_DATA_FILES:
            destination = root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                destination.write_text(_git_text("show", f"{revision}:{relative_path}"), encoding="utf-8")
            except subprocess.CalledProcessError:
                destination.write_text("{}\n" if relative_path.endswith(".json") else "Draw,Date,N1,N2,N3,N4,N5,N6,Special\n", encoding="utf-8")
        snapshot = build_daily_status_snapshot(
            draw_history_path=root / "data/lotto_history_real.csv",
            blind_history_path=root / "data/blind_test_history.json",
            brier_history_path=root / "data/brier_tracking_history.json",
            weight_history_path=root / "data/weight_adjustment_history.json",
            latest_prediction_path=root / "data/latest_prediction.json",
        )
    report_date_hkt, generated_at_hkt = event_timestamp_hkt(event_timestamp)
    snapshot["report_date_hkt"] = report_date_hkt
    snapshot["generated_at_hkt"] = generated_at_hkt
    return snapshot


def backfill(ledger_path: Path = DEFAULT_EVENT_LEDGER_PATH, archive_path: Path = DEFAULT_DAILY_REPORT_ARCHIVE_PATH) -> dict[str, int]:
    result = {"eligible": 0, "created": 0, "skipped": 0, "unavailable": 0}
    for event in _sent_daily_events(ledger_path):
        result["eligible"] += 1
        event_id = str(event.get("event_id", ""))
        sent_at = str(event.get("sent_at"))
        revision = _commit_for_timestamp(sent_at)
        if not event_id or not revision:
            result["unavailable"] += 1
            continue
        snapshot = _snapshot_at_revision(revision, sent_at)
        report, created = append_reconstructed_daily_report(
            event_id,
            snapshot,
            render_daily_status_body(snapshot),
            render_daily_status_html(snapshot),
            source_revision=revision,
            source_event_sent_at_utc=sent_at,
            refresh_reconstruction=True,
            path=archive_path,
        )
        if created:
            result["created"] += 1
        elif report:
            result["skipped"] += 1
    return result


if __name__ == "__main__":
    outcome = backfill()
    print("歷史每日報告回填完成：" + "；".join(f"{key}={value}" for key, value in outcome.items()))
