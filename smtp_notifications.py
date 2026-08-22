"""Root-invoked Gmail SMTP dispatch for formally qualified weight events.

The module never computes or activates weights. It only turns pre-existing,
append-only weight versions into idempotent email events after the formal
qualification gate has been recorded by the governance workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable

from weight_monitor import CONFIG_LABELS, DEFAULT_WEIGHT_HISTORY_PATH, load_weight_adjustment_history


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_EVENT_LEDGER_PATH = PROJECT_ROOT / "data" / "weight_notification_events.json"
MAX_ATTEMPTS = 3
FORMAL_STATUSES = {"frozen", "confirmed", "activated", "rolled_back"}


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


def main() -> None:
    parser = argparse.ArgumentParser(description="派送 Mark Six 正式權重事件的 Gmail SMTP 通知。")
    parser.add_argument("--dispatch", action="store_true", help="派送符合正式資格且尚未寄出的事件。")
    parser.add_argument("--send-test", action="store_true", help="寄出單次 SMTP 測試信。")
    parser.add_argument("--weight-history", type=Path, default=DEFAULT_WEIGHT_HISTORY_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_EVENT_LEDGER_PATH)
    args = parser.parse_args()
    if args.dispatch == args.send_test:
        parser.error("請指定 --dispatch 或 --send-test 其中之一。")
    settings = smtp_settings_from_environment()
    if args.send_test:
        send_test(settings)
        print("SMTP 測試信已提交至寄件伺服器。")
        return
    result = dispatch_events(settings, weight_history_path=args.weight_history, ledger_path=args.ledger)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
