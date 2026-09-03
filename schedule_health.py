"""Append-only, non-sensitive health summaries for the daily Mark Six scheduler.

The module records execution timing and step outcomes only.  It never reads SMTP
credentials, sends email, fetches results, or alters prediction and governance
ledgers.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SCHEDULE_HEALTH_PATH = PROJECT_ROOT / "data" / "schedule_health_summary.json"
HONG_KONG_TZ = ZoneInfo("Asia/Hong_Kong")
MAX_RUN_HISTORY = 31
RUN_STATUSES = {"running", "completed", "degraded", "failed"}
STEP_STATUSES = {"completed", "failed", "skipped"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _hkt_now() -> str:
    return datetime.now(HONG_KONG_TZ).isoformat()


def _empty_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "purpose": "每日排程可觀測性摘要；不包含 SMTP 憑證、收件者或正式研究帳本內容。",
        "latest": None,
        "runs": [],
    }


def load_schedule_health(path: Path = DEFAULT_SCHEDULE_HEALTH_PATH) -> dict[str, Any]:
    """Load a non-sensitive scheduler summary; malformed files fail closed to empty."""
    if not path.exists():
        return _empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_payload()
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), list):
        return _empty_payload()
    records = [record for record in payload["runs"] if isinstance(record, dict)]
    latest = payload.get("latest")
    return {
        "schema_version": 1,
        "purpose": _empty_payload()["purpose"],
        "latest": latest if isinstance(latest, dict) else (records[-1] if records else None),
        "runs": records[-MAX_RUN_HISTORY:],
    }


def _save_schedule_health(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["runs"] = payload.get("runs", [])[-MAX_RUN_HISTORY:]
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o640)
    temporary.replace(path)


def _sanitise_detail(detail: str) -> str:
    return " ".join(str(detail).split())[:240]


def _find_run(payload: dict[str, Any], run_id: str) -> dict[str, Any]:
    for record in payload["runs"]:
        if str(record.get("run_id")) == run_id:
            return record
    raise ValueError(f"找不到排程執行紀錄：{run_id}")


def begin_schedule_run(
    run_id: str,
    scheduled_for_hkt: str,
    *,
    path: Path = DEFAULT_SCHEDULE_HEALTH_PATH,
    started_at_utc: str | None = None,
    started_at_hkt: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Create one run record. A repeated run ID is safely returned unchanged."""
    identifier = str(run_id).strip()
    if not identifier:
        raise ValueError("排程執行 ID 不可留空。")
    payload = load_schedule_health(path)
    for record in payload["runs"]:
        if str(record.get("run_id")) == identifier:
            return copy.deepcopy(record), False
    record = {
        "run_id": identifier,
        "scheduled_for_hkt": str(scheduled_for_hkt),
        "started_at_utc": started_at_utc or _utc_now(),
        "started_at_hkt": started_at_hkt or _hkt_now(),
        "completed_at_utc": None,
        "completed_at_hkt": None,
        "status": "running",
        "data_changed": None,
        "steps": [],
        "detail": "daily cron started",
    }
    payload["runs"].append(record)
    payload["latest"] = record
    _save_schedule_health(payload, path)
    return copy.deepcopy(record), True


def record_schedule_step(
    run_id: str,
    name: str,
    status: str,
    *,
    exit_code: int | None,
    duration_seconds: int | None,
    detail: str = "",
    path: Path = DEFAULT_SCHEDULE_HEALTH_PATH,
    recorded_at_utc: str | None = None,
) -> dict[str, Any]:
    """Add or replace one named non-sensitive step outcome for a scheduled run."""
    if status not in STEP_STATUSES:
        raise ValueError(f"不支援的排程步驟狀態：{status}")
    payload = load_schedule_health(path)
    record = _find_run(payload, str(run_id))
    step = {
        "name": str(name).strip() or "unnamed_step",
        "status": status,
        "exit_code": int(exit_code) if exit_code is not None else None,
        "duration_seconds": max(0, int(duration_seconds or 0)),
        "detail": _sanitise_detail(detail),
        "recorded_at_utc": recorded_at_utc or _utc_now(),
    }
    record["steps"] = [item for item in record.get("steps", []) if item.get("name") != step["name"]]
    record["steps"].append(step)
    payload["latest"] = record
    _save_schedule_health(payload, path)
    return copy.deepcopy(record)


def record_data_change(
    run_id: str,
    changed: bool,
    *,
    path: Path = DEFAULT_SCHEDULE_HEALTH_PATH,
) -> dict[str, Any]:
    payload = load_schedule_health(path)
    record = _find_run(payload, str(run_id))
    record["data_changed"] = bool(changed)
    payload["latest"] = record
    _save_schedule_health(payload, path)
    return copy.deepcopy(record)


def finish_schedule_run(
    run_id: str,
    status: str,
    *,
    detail: str = "",
    path: Path = DEFAULT_SCHEDULE_HEALTH_PATH,
    completed_at_utc: str | None = None,
    completed_at_hkt: str | None = None,
) -> dict[str, Any]:
    if status not in RUN_STATUSES - {"running"}:
        raise ValueError(f"不支援的排程完成狀態：{status}")
    payload = load_schedule_health(path)
    record = _find_run(payload, str(run_id))
    record.update(
        {
            "status": status,
            "detail": _sanitise_detail(detail),
            "completed_at_utc": completed_at_utc or _utc_now(),
            "completed_at_hkt": completed_at_hkt or _hkt_now(),
        }
    )
    payload["latest"] = record
    _save_schedule_health(payload, path)
    return copy.deepcopy(record)


def schedule_health_index(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Return dashboard-safe, newest-first index rows without sensitive data."""
    rows: list[dict[str, str]] = []
    for record in reversed(payload.get("runs", [])):
        if not isinstance(record, dict):
            continue
        data_changed = record.get("data_changed")
        data_label = "已變更" if data_changed is True else "未變更" if data_changed is False else "未完成"
        steps = record.get("steps", [])
        step_text = "；".join(
            f"{item.get('name', '未命名')}：{item.get('status', '未知')}"
            for item in steps
            if isinstance(item, dict)
        ) or "尚未記錄"
        rows.append(
            {
                "排程時間（香港）": str(record.get("scheduled_for_hkt", "—")),
                "開始時間（香港）": str(record.get("started_at_hkt", "—")),
                "完成時間（香港）": str(record.get("completed_at_hkt") or "進行中"),
                "整體狀態": str(record.get("status", "未知")),
                "資料結果": data_label,
                "步驟摘要": step_text,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="記錄 Mark Six 每日排程健康摘要；不派送 Email。")
    parser.add_argument("--path", type=Path, default=DEFAULT_SCHEDULE_HEALTH_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    start.add_argument("--run-id", required=True)
    start.add_argument("--scheduled-for-hkt", required=True)

    step = commands.add_parser("step")
    step.add_argument("--run-id", required=True)
    step.add_argument("--name", required=True)
    step.add_argument("--status", choices=sorted(STEP_STATUSES), required=True)
    step.add_argument("--exit-code", type=int)
    step.add_argument("--duration-seconds", type=int)
    step.add_argument("--detail", default="")

    data_change = commands.add_parser("data-change")
    data_change.add_argument("--run-id", required=True)
    data_change.add_argument("--changed", choices=("true", "false"), required=True)

    finish = commands.add_parser("finish")
    finish.add_argument("--run-id", required=True)
    finish.add_argument("--status", choices=sorted(RUN_STATUSES - {"running"}), required=True)
    finish.add_argument("--detail", default="")

    args = parser.parse_args()
    if args.command == "start":
        begin_schedule_run(args.run_id, args.scheduled_for_hkt, path=args.path)
    elif args.command == "step":
        record_schedule_step(
            args.run_id,
            args.name,
            args.status,
            exit_code=args.exit_code,
            duration_seconds=args.duration_seconds,
            detail=args.detail,
            path=args.path,
        )
    elif args.command == "data-change":
        record_data_change(args.run_id, args.changed == "true", path=args.path)
    elif args.command == "finish":
        finish_schedule_run(args.run_id, args.status, detail=args.detail, path=args.path)


if __name__ == "__main__":
    main()
