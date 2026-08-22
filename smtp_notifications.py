"""Root-invoked Gmail SMTP dispatch for formally qualified weight events.

The module never computes or activates weights. It only turns pre-existing,
append-only weight versions into idempotent email events after the formal
qualification gate has been recorded by the governance workflow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from weight_monitor import CONFIG_LABELS, DEFAULT_WEIGHT_HISTORY_PATH, load_weight_adjustment_history


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_EVENT_LEDGER_PATH = PROJECT_ROOT / "data" / "weight_notification_events.json"
DEFAULT_DRAW_HISTORY_PATH = PROJECT_ROOT / "data" / "lotto_history_real.csv"
DEFAULT_BLIND_HISTORY_PATH = PROJECT_ROOT / "data" / "blind_test_history.json"
DEFAULT_BRIER_HISTORY_PATH = PROJECT_ROOT / "data" / "brier_tracking_history.json"
MAX_ATTEMPTS = 3
FORMAL_STATUSES = {"frozen", "confirmed", "activated", "rolled_back"}
HONG_KONG_TZ = ZoneInfo("Asia/Hong_Kong")


class NotificationConfigurationError(RuntimeError):
    """Raised when SMTP settings are not safely configured."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _weights(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, dict) or set(raw) != set(CONFIG_LABELS):
        return None
    try:
        values = {key: float(raw[key]) for key in CONFIG_LABELS}
    except (TypeError, ValueError):
        return None
    if any(value < 0.10 - 1e-9 or value > 0.55 + 1e-9 for value in values.values()):
        return None
    return values if abs(sum(values.values()) - 1.0) <= 1e-6 else None


def load_event_ledger(path: Path = DEFAULT_EVENT_LEDGER_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "events": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "events": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        return {"schema_version": 1, "events": []}
    return payload


def save_event_ledger(payload: dict[str, Any], path: Path = DEFAULT_EVENT_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def event_id(version: str, event_type: str, marker: str) -> str:
    source = f"{version}|{event_type}|{marker}".encode("utf-8")
    return hashlib.sha256(source).hexdigest()[:24]


def collect_weight_events(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only formal, pre-recorded lifecycle events; do not infer eligibility."""
    events: list[dict[str, Any]] = []
    previous_weights: dict[str, float] | None = None
    for record in records:
        weights = _weights(record.get("proposed_weights"))
        status = str(record.get("status", ""))
        version = str(record.get("version", "")).strip()
        qualified = record.get("formal_qualification_passed") is True
        if not version or weights is None:
            continue
        if qualified and status in FORMAL_STATUSES:
            marker = str(record.get("locked_at") or record.get("activated_at") or version)
            event_type = {
                "frozen": "freeze_started",
                "confirmed": "freeze_confirmed",
                "activated": "weight_activated",
                "rolled_back": "weight_rolled_back",
            }[status]
            events.append(
                {
                    "event_id": event_id(version, event_type, marker),
                    "event_type": event_type,
                    "version": version,
                    "marker": marker,
                    "record": record,
                    "previous_weights": previous_weights,
                    "weights": weights,
                }
            )
            completed = int(record.get("freeze_completed_draws", 0) or 0)
            for milestone in (25, 50):
                if completed >= milestone:
                    milestone_type = f"freeze_{milestone}_draws"
                    events.append(
                        {
                            "event_id": event_id(version, milestone_type, marker),
                            "event_type": milestone_type,
                            "version": version,
                            "marker": marker,
                            "record": record,
                            "previous_weights": previous_weights,
                            "weights": weights,
                        }
                    )
        previous_weights = weights
    return events


def _format_weights(weights: dict[str, float] | None) -> str:
    if not weights:
        return "無前一個正式權重版本"
    return "；".join(f"{CONFIG_LABELS[key]} {weights[key]:.1%}" for key in CONFIG_LABELS)


def render_subject(event: dict[str, Any]) -> str:
    labels = {
        "freeze_started": "權重凍結盲測已開始",
        "freeze_25_draws": "權重凍結盲測完成 25 期",
        "freeze_50_draws": "權重凍結盲測完成 50 期",
        "freeze_confirmed": "權重凍結確認完成",
        "weight_activated": "正式權重版本已啟用",
        "weight_rolled_back": "權重版本已回退",
    }
    return f"[Mark Six] {labels[event['event_type']]} — {event['version']}"


def render_body(event: dict[str, Any]) -> str:
    record = event["record"]
    completed = int(record.get("freeze_completed_draws", 0) or 0)
    return "\n".join(
        [
            "這是 Mark Six 四配置權重治理系統的自動通知。",
            "",
            f"事件：{event['event_type']}",
            f"權重版本：{event['version']}",
            f"唯一事件 ID：{event['event_id']}",
            f"記錄時間：{event['marker']}",
            f"凍結確認進度：{completed}/50 期",
            "",
            "新權重：",
            _format_weights(event["weights"]),
            "",
            "前一版本權重：",
            _format_weights(event["previous_weights"]),
            "",
            "此事件只會在正式資格閘門已被預先註冊程序標記為通過後產生。"
            "系統以事件 ID 防止每日重跑時重複寄送。",
            "本通知僅供統計實驗治理與審計用途，不構成投注建議或中獎保證。",
        ]
    )


def smtp_settings_from_environment() -> dict[str, Any]:
    required = ("MARK_SIX_SMTP_USERNAME", "MARK_SIX_SMTP_PASSWORD", "MARK_SIX_SMTP_TO")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise NotificationConfigurationError("缺少 SMTP 設定：" + ", ".join(missing))
    try:
        port = int(os.environ.get("MARK_SIX_SMTP_PORT", "465"))
    except ValueError as error:
        raise NotificationConfigurationError("MARK_SIX_SMTP_PORT 必須是整數。") from error
    return {
        "host": os.environ.get("MARK_SIX_SMTP_HOST", "smtp.gmail.com"),
        "port": port,
        "username": os.environ["MARK_SIX_SMTP_USERNAME"],
        "password": os.environ["MARK_SIX_SMTP_PASSWORD"],
        "sender": os.environ.get("MARK_SIX_SMTP_FROM", os.environ["MARK_SIX_SMTP_USERNAME"]),
        "recipient": os.environ["MARK_SIX_SMTP_TO"],
    }


def send_email(settings: dict[str, Any], subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings["sender"]
    message["To"] = settings["recipient"]
    message["Subject"] = subject
    message.set_content(body)
    timeout = 25
    if int(settings["port"]) == 465:
        with smtplib.SMTP_SSL(settings["host"], int(settings["port"]), timeout=timeout) as client:
            client.login(settings["username"], settings["password"])
            client.send_message(message)
    else:
        with smtplib.SMTP(settings["host"], int(settings["port"]), timeout=timeout) as client:
            client.starttls()
            client.login(settings["username"], settings["password"])
            client.send_message(message)


def dispatch_events(
    settings: dict[str, Any],
    *,
    weight_history_path: Path = DEFAULT_WEIGHT_HISTORY_PATH,
    ledger_path: Path = DEFAULT_EVENT_LEDGER_PATH,
    send_func: Callable[[dict[str, Any], str, str], None] = send_email,
) -> dict[str, int]:
    records = load_weight_adjustment_history(weight_history_path)
    ledger = load_event_ledger(ledger_path)
    ledger_events = {str(item.get("event_id")): item for item in ledger["events"] if isinstance(item, dict)}
    result = {"eligible": 0, "sent": 0, "skipped": 0, "failed": 0}
    for event in collect_weight_events(records):
        result["eligible"] += 1
        prior = ledger_events.get(event["event_id"])
        if prior and prior.get("status") == "sent":
            result["skipped"] += 1
            continue
        attempts = int(prior.get("attempts", 0)) if prior else 0
        if attempts >= MAX_ATTEMPTS:
            result["failed"] += 1
            continue
        entry = prior or {"event_id": event["event_id"], "created_at": utc_now(), "attempts": 0}
        try:
            send_func(settings, render_subject(event), render_body(event))
            entry.update({"status": "sent", "attempts": attempts + 1, "sent_at": utc_now(), "last_error": None})
            result["sent"] += 1
        except Exception as error:  # noqa: BLE001 - delivery errors are recorded, not hidden
            entry.update({"status": "failed", "attempts": attempts + 1, "last_attempt_at": utc_now(), "last_error": str(error)[:500]})
            result["failed"] += 1
        ledger_events[event["event_id"]] = entry
    ledger["events"] = list(ledger_events.values())
    ledger["updated_at"] = utc_now()
    save_event_ledger(ledger, ledger_path)
    return result


def send_test(settings: dict[str, Any]) -> None:
    send_email(
        settings,
        "[測試] Mark Six Cloud SMTP 權重通知",
        "這是由 Cloud Computer 的獨立 Gmail SMTP 通知機制寄出的受控測試信。\n\n"
        "此信驗證 root-only SMTP 設定、TLS 登入與投遞流程。沒有任何正式權重調整已被觸發。",
    )


def _load_json(path: Path, list_key: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    values = payload.get(list_key, []) if isinstance(payload, dict) else []
    return [value for value in values if isinstance(value, dict)] if isinstance(values, list) else []


def _latest_official_draw(path: Path = DEFAULT_DRAW_HISTORY_PATH) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return None
    if not rows:
        return None
    latest = rows[-1]
    numbers = [latest.get(f"N{index}", "") for index in range(1, 7)]
    return {"draw": latest.get("Draw", "未知"), "date": latest.get("Date", "未知"), "numbers": numbers}


def build_daily_status_snapshot(
    *,
    draw_history_path: Path = DEFAULT_DRAW_HISTORY_PATH,
    blind_history_path: Path = DEFAULT_BLIND_HISTORY_PATH,
    brier_history_path: Path = DEFAULT_BRIER_HISTORY_PATH,
    weight_history_path: Path = DEFAULT_WEIGHT_HISTORY_PATH,
) -> dict[str, Any]:
    """Read-only daily status snapshot; never alters blind or weight records."""
    blind_records = _load_json(blind_history_path, "blind_tests")
    brier_records = _load_json(brier_history_path, "records")
    weight_records = load_weight_adjustment_history(weight_history_path)
    latest_weight = weight_records[-1] if weight_records else None
    pending_blind = [record for record in blind_records if record.get("status") == "locked_pending_result"]
    pending_brier = [record for record in brier_records if record.get("status") == "locked_pending_result"]
    now_hkt = datetime.now(HONG_KONG_TZ)
    return {
        "report_date_hkt": now_hkt.date().isoformat(),
        "generated_at_hkt": now_hkt.isoformat(),
        "latest_official_draw": _latest_official_draw(draw_history_path),
        "latest_blind": pending_blind[-1] if pending_blind else (blind_records[-1] if blind_records else None),
        "latest_brier": pending_brier[-1] if pending_brier else (brier_records[-1] if brier_records else None),
        "weight_version": latest_weight,
        "common_brier_draws": 0,
        "formal_gate": "等待四配置共同已結算盲測期數達 100 期",
    }


def _number_text(values: Any) -> str:
    if not isinstance(values, list):
        return "未提供"
    return "、".join(str(value).zfill(2) for value in values)


def render_daily_status_body(snapshot: dict[str, Any], *, simulation: bool = False) -> str:
    latest = snapshot.get("latest_official_draw") or {}
    blind = snapshot.get("latest_blind") or {}
    brier = snapshot.get("latest_brier") or {}
    weights = snapshot.get("weight_version") or {}
    variants = blind.get("variants", []) if isinstance(blind.get("variants"), list) else []
    variant_lines = [
        f"- {item.get('label', item.get('key', '未命名'))}：{_number_text(item.get('numbers'))}"
        for item in variants
        if isinstance(item, dict)
    ]
    weight_values = _weights(weights.get("proposed_weights")) if isinstance(weights, dict) else None
    simulation_heading = "【受控模擬通知】\n本信只驗證格式，沒有建立、結算或改寫任何正式盲測與權重版本。\n\n" if simulation else ""
    return "\n".join(
        [
            simulation_heading + "Mark Six 每日盲測結果與模型權重狀態摘要",
            f"報告時間（香港）：{snapshot.get('generated_at_hkt', '未知')}",
            "",
            "一、最新官方結果資料",
            f"最新期數：{latest.get('draw', '未知')}；日期：{latest.get('date', '未知')}",
            f"六個正選：{_number_text(latest.get('numbers'))}",
            "",
            "二、三配置盲測狀態",
            f"目標期數：{blind.get('target_draw', '尚未鎖定')}；狀態：{blind.get('status', '無記錄')}",
            *(variant_lines or ["- 目前沒有可呈現的三配置盲測記錄"]),
            "",
            "三、四配置 Brier 追蹤",
            f"目標期數：{brier.get('target_draw', '尚未鎖定')}；狀態：{brier.get('status', '無記錄')}",
            f"共同已結算期數：{snapshot.get('common_brier_draws', 0)}；正式閘門：{snapshot.get('formal_gate')}",
            "",
            "四、模型權重與凍結狀態",
            f"權重版本：{weights.get('version', 'baseline-equal-v1（觀察期）') if isinstance(weights, dict) else 'baseline-equal-v1（觀察期）'}",
            f"凍結進度：{weights.get('freeze_completed_draws', 0) if isinstance(weights, dict) else 0}/50 期",
            f"權重：{_format_weights(weight_values) if weight_values else '四配置等權重 25.0%／25.0%／25.0%／25.0%'}",
            "",
            "本報告僅供統計實驗、盲測治理與系統審計用途，不構成投注建議或中獎保證。",
        ]
    )


def dispatch_daily_status(
    settings: dict[str, Any],
    *,
    ledger_path: Path = DEFAULT_EVENT_LEDGER_PATH,
    snapshot: dict[str, Any] | None = None,
    send_func: Callable[[dict[str, Any], str, str], None] = send_email,
) -> dict[str, int]:
    snapshot = snapshot or build_daily_status_snapshot()
    report_date = str(snapshot["report_date_hkt"])
    daily_event = event_id("daily-status", "daily_summary", report_date)
    ledger = load_event_ledger(ledger_path)
    entries = {str(item.get("event_id")): item for item in ledger["events"] if isinstance(item, dict)}
    prior = entries.get(daily_event)
    if prior and prior.get("status") == "sent":
        return {"sent": 0, "skipped": 1, "failed": 0}
    attempts = int(prior.get("attempts", 0)) if prior else 0
    if attempts >= MAX_ATTEMPTS:
        return {"sent": 0, "skipped": 0, "failed": 1}
    entry = prior or {"event_id": daily_event, "event_type": "daily_summary", "created_at": utc_now(), "attempts": 0}
    try:
        send_func(settings, f"[Mark Six] 每日盲測與權重狀態 — {report_date}", render_daily_status_body(snapshot))
        entry.update({"status": "sent", "attempts": attempts + 1, "sent_at": utc_now(), "last_error": None})
        result = {"sent": 1, "skipped": 0, "failed": 0}
    except Exception as error:  # noqa: BLE001
        entry.update({"status": "failed", "attempts": attempts + 1, "last_attempt_at": utc_now(), "last_error": str(error)[:500]})
        result = {"sent": 0, "skipped": 0, "failed": 1}
    entries[daily_event] = entry
    ledger["events"] = list(entries.values())
    ledger["updated_at"] = utc_now()
    save_event_ledger(ledger, ledger_path)
    return result


def send_simulated_daily_status(settings: dict[str, Any]) -> None:
    snapshot = build_daily_status_snapshot()
    send_email(
        settings,
        f"[模擬] Mark Six 盲測與權重凍結狀態 — {snapshot['report_date_hkt']}",
        render_daily_status_body(snapshot, simulation=True),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="派送 Mark Six 正式權重事件的 Gmail SMTP 通知。")
    parser.add_argument("--dispatch", action="store_true", help="派送符合正式資格且尚未寄出的事件。")
    parser.add_argument("--daily-summary", action="store_true", help="寄送每日盲測與權重狀態摘要。")
    parser.add_argument("--send-simulation", action="store_true", help="寄送不影響正式紀錄的受控每日摘要模擬信。")
    parser.add_argument("--send-test", action="store_true", help="寄出單次 SMTP 測試信。")
    parser.add_argument("--weight-history", type=Path, default=DEFAULT_WEIGHT_HISTORY_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_EVENT_LEDGER_PATH)
    args = parser.parse_args()
    selected = sum((args.dispatch, args.daily_summary, args.send_simulation, args.send_test))
    if selected != 1:
        parser.error("請指定 --dispatch、--daily-summary、--send-simulation 或 --send-test 其中之一。")
    settings = smtp_settings_from_environment()
    if args.send_test:
        send_test(settings)
        print("SMTP 測試信已提交至寄件伺服器。")
        return
    if args.send_simulation:
        send_simulated_daily_status(settings)
        print("每日摘要模擬信已提交至寄件伺服器。")
        return
    if args.daily_summary:
        print(json.dumps(dispatch_daily_status(settings), ensure_ascii=False))
        return
    result = dispatch_events(settings, weight_history_path=args.weight_history, ledger_path=args.ledger)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
