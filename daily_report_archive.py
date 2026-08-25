"""Append-only archive for successfully submitted daily Mark Six reports.

The archive stores the exact read-only snapshot and two report renderings used
for the daily email. It never changes prediction, blind-test, Brier, or weight
ledgers. A record may only move from ``prepared`` to ``sent`` after SMTP has
accepted the daily report; the immutable report content is never rewritten.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DAILY_REPORT_ARCHIVE_PATH = PROJECT_ROOT / "data" / "daily_report_archive.json"
ARCHIVE_SCHEMA_VERSION = 1
DISPLAYABLE_DELIVERY_STATUSES = {"sent", "sent_reconstructed"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_daily_report_archive(path: Path = DEFAULT_DAILY_REPORT_ARCHIVE_PATH) -> list[dict[str, Any]]:
    """Return safely parsed archive records, newest first at display time."""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    records = payload.get("reports", []) if isinstance(payload, dict) else []
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def _write_daily_report_archive(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "purpose": "已提交每日研究報告的唯讀歸檔，只供統計教育、盲測治理與系統審計用途。",
        "reports": sorted(records, key=lambda item: str(item.get("generated_at_hkt", ""))),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare_daily_report_archive(
    archive_id: str,
    snapshot: dict[str, Any],
    plain_body: str,
    html_body: str,
    *,
    path: Path = DEFAULT_DAILY_REPORT_ARCHIVE_PATH,
) -> tuple[dict[str, Any], bool]:
    """Append an immutable prepared report once per daily event identifier."""
    records = load_daily_report_archive(path)
    for record in records:
        if str(record.get("archive_id")) == archive_id:
            return record, False
    latest_draw = snapshot.get("latest_official_draw") if isinstance(snapshot.get("latest_official_draw"), dict) else {}
    record = {
        "archive_id": archive_id,
        "report_date_hkt": str(snapshot.get("report_date_hkt", "")),
        "generated_at_hkt": str(snapshot.get("generated_at_hkt", "")),
        "prepared_at_utc": _utc_now(),
        "delivery_status": "prepared",
        "latest_draw": str(latest_draw.get("draw", "未知")),
        "snapshot": snapshot,
        "plain_body": plain_body,
        "html_body": html_body,
    }
    records.append(record)
    _write_daily_report_archive(records, path)
    return record, True


def mark_daily_report_sent(
    archive_id: str,
    *,
    path: Path = DEFAULT_DAILY_REPORT_ARCHIVE_PATH,
) -> bool:
    """Mark a prepared archive as sent without changing its report snapshot."""
    records = load_daily_report_archive(path)
    changed = False
    for record in records:
        if str(record.get("archive_id")) != archive_id:
            continue
        if record.get("delivery_status") != "sent":
            record["delivery_status"] = "sent"
            record["sent_at_utc"] = _utc_now()
            changed = True
        break
    if changed:
        _write_daily_report_archive(records, path)
    return changed


def append_reconstructed_daily_report(
    archive_id: str,
    snapshot: dict[str, Any],
    plain_body: str,
    html_body: str,
    *,
    source_revision: str,
    source_event_sent_at_utc: str,
    path: Path = DEFAULT_DAILY_REPORT_ARCHIVE_PATH,
) -> tuple[dict[str, Any], bool]:
    """Append a clearly labelled reconstruction of a previously sent legacy report.

    Legacy events recorded successful submission but did not preserve the MIME
    content. This helper stores a reproducible rendering from the Git revision
    available at the time, without sending mail or touching formal ledgers.
    """
    records = load_daily_report_archive(path)
    for record in records:
        if str(record.get("archive_id")) == archive_id:
            return record, False
    latest_draw = snapshot.get("latest_official_draw") if isinstance(snapshot.get("latest_official_draw"), dict) else {}
    record = {
        "archive_id": archive_id,
        "report_date_hkt": str(snapshot.get("report_date_hkt", "")),
        "generated_at_hkt": str(snapshot.get("generated_at_hkt", "")),
        "prepared_at_utc": _utc_now(),
        "delivery_status": "sent_reconstructed",
        "content_provenance": "依既有成功提交事件及當時 Git 修訂重建；非原始 MIME 保存檔。",
        "source_revision": source_revision,
        "source_event_sent_at_utc": source_event_sent_at_utc,
        "latest_draw": str(latest_draw.get("draw", "未知")),
        "snapshot": snapshot,
        "plain_body": plain_body,
        "html_body": html_body,
    }
    records.append(record)
    _write_daily_report_archive(records, path)
    return record, True


def search_daily_report_archive(
    records: list[dict[str, Any]],
    *,
    query: str = "",
    report_date: str | None = None,
    latest_draw: str = "",
) -> list[dict[str, Any]]:
    """Search sent reports by text, HKT report date, and official draw number."""
    normalized_query = query.strip().casefold()
    normalized_draw = latest_draw.strip()
    matched: list[dict[str, Any]] = []
    for record in records:
        if record.get("delivery_status") not in DISPLAYABLE_DELIVERY_STATUSES:
            continue
        if report_date and str(record.get("report_date_hkt", "")) != report_date:
            continue
        if normalized_draw and normalized_draw not in str(record.get("latest_draw", "")):
            continue
        haystack = "\n".join(
            [
                str(record.get("archive_id", "")),
                str(record.get("report_date_hkt", "")),
                str(record.get("latest_draw", "")),
                str(record.get("plain_body", "")),
            ]
        ).casefold()
        if normalized_query and normalized_query not in haystack:
            continue
        matched.append(record)
    return sorted(matched, key=lambda item: str(item.get("generated_at_hkt", "")), reverse=True)


def daily_report_archive_index(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build compact, user-facing rows without exposing the full stored HTML."""
    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: str(item.get("generated_at_hkt", "")), reverse=True):
        if record.get("delivery_status") not in DISPLAYABLE_DELIVERY_STATUSES:
            continue
        snapshot = record.get("snapshot") if isinstance(record.get("snapshot"), dict) else {}
        summary = snapshot.get("recent_blind_hit_summary") if isinstance(snapshot.get("recent_blind_hit_summary"), dict) else {}
        prediction = snapshot.get("latest_prediction") if isinstance(snapshot.get("latest_prediction"), dict) else {}
        recommendations = prediction.get("top_5_recommendations", []) if isinstance(prediction.get("top_5_recommendations"), list) else []
        first = recommendations[0] if recommendations and isinstance(recommendations[0], dict) else {}
        rows.append(
            {
                "歸檔日期": record.get("report_date_hkt", "—"),
                "報告時間（香港）": record.get("generated_at_hkt", "—"),
                "最新官方期數": record.get("latest_draw", "—"),
                "近期已結算盲測期數": summary.get("settled_draws", 0),
                "近期平均最高命中": f"{float(summary.get('average_best_hits', 0.0)):.2f}/6",
                "第一組相對強度": f"{int(first.get('relative_strength_percent', 0))}%" if first else "—",
                "內容來源": "原始提交快照" if record.get("delivery_status") == "sent" else "歷史可追溯重建",
                "歸檔 ID": record.get("archive_id", "—"),
            }
        )
    return rows
