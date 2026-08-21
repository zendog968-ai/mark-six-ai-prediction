"""Read-only monitoring helpers for constrained Brier weight proposals.

The monitor never fabricates a proposal.  It shows equal baseline weights until
an externally approved, append-only frozen-weight record is available.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from brier_dashboard import CONFIG_LABELS


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_WEIGHT_HISTORY_PATH = PROJECT_ROOT / "data" / "weight_adjustment_history.json"
MINIMUM_COMMON_DRAWS = 100
FREEZE_CONFIRMATION_DRAWS = 50
DEFAULT_WEIGHTS = {key: 1.0 / len(CONFIG_LABELS) for key in CONFIG_LABELS}


def load_weight_adjustment_history(path: Path = DEFAULT_WEIGHT_HISTORY_PATH) -> list[dict[str, Any]]:
    """Load append-only weight versions; malformed files yield no active versions."""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    records = payload.get("records", []) if isinstance(payload, dict) else []
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def _normalise_weights(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, dict) or set(raw) != set(CONFIG_LABELS):
        return None
    try:
        weights = {key: float(raw[key]) for key in CONFIG_LABELS}
    except (TypeError, ValueError):
        return None
    if any(weight < 0.10 - 1e-9 or weight > 0.55 + 1e-9 for weight in weights.values()):
        return None
    return weights if abs(sum(weights.values()) - 1.0) <= 1e-6 else None


def _latest_valid_version(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = []
    for record in records:
        weights = _normalise_weights(record.get("proposed_weights"))
        if weights is None:
            continue
        record = {**record, "proposed_weights": weights}
        valid.append(record)
    return valid[-1] if valid else None


def build_weight_monitor_state(
    brier_frame: pd.DataFrame,
    records: list[dict[str, Any]],
    *,
    minimum_common_draws: int = MINIMUM_COMMON_DRAWS,
    freeze_confirmation_draws: int = FREEZE_CONFIRMATION_DRAWS,
) -> dict[str, Any]:
    """Build display-only state without triggering optimisation or activation."""
    completed = int(len(brier_frame))
    latest = _latest_valid_version(records)
    current_weights = latest["proposed_weights"] if latest else DEFAULT_WEIGHTS.copy()
    status = "凍結盲測中" if latest and latest.get("status") == "frozen" else "累積共同盲測中"
    freeze_completed = int(latest.get("freeze_completed_draws", 0)) if latest else 0
    freeze_completed = max(0, min(freeze_completed, freeze_confirmation_draws))
    next_gate_remaining = max(0, minimum_common_draws - completed)
    gate_rows = [
        {"資格條件": "共同已結算完整機率期數", "要求": f"至少 {minimum_common_draws} 期", "目前": completed, "狀態": "通過" if completed >= minimum_common_draws else "等待"},
        {"資格條件": "Bootstrap＋Holm", "要求": "校正後 p < 0.05 且 95% CI 上界 < 0", "目前": "尚未正式檢定" if completed < minimum_common_draws else "需由預先註冊程序確認", "狀態": "等待"},
        {"資格條件": "Diebold–Mariano＋Holm", "要求": "校正後單向 p < 0.05，方向一致", "目前": "尚未正式檢定" if completed < minimum_common_draws else "需由預先註冊程序確認", "狀態": "等待"},
        {"資格條件": "實際效應量", "要求": "Brier Skill Score ≥ +0.5%", "目前": "尚未正式檢定", "狀態": "等待"},
    ]
    weight_rows = [
        {
            "配置": CONFIG_LABELS[key],
            "目前權重": current_weights[key],
            "權重來源": latest.get("version", "baseline-equal-v1") if latest else "baseline-equal-v1（觀察期）",
        }
        for key in CONFIG_LABELS
    ]
    history_rows = []
    for record in records:
        weights = _normalise_weights(record.get("proposed_weights"))
        if weights is None:
            continue
        row = {
            "版本": record.get("version", "—"),
            "鎖定時間": record.get("locked_at", "—"),
            "狀態": record.get("status", "—"),
            "凍結確認進度": f"{max(0, int(record.get('freeze_completed_draws', 0)))}/{freeze_confirmation_draws}",
        }
        row.update({CONFIG_LABELS[key]: weights[key] for key in CONFIG_LABELS})
        history_rows.append(row)
    return {
        "completed_common_draws": completed,
        "next_gate_remaining": next_gate_remaining,
        "status": status,
        "active_version": latest.get("version", "baseline-equal-v1") if latest else "baseline-equal-v1",
        "freeze_completed_draws": freeze_completed,
        "freeze_confirmation_draws": freeze_confirmation_draws,
        "weight_rows": pd.DataFrame(weight_rows),
        "gate_rows": pd.DataFrame(gate_rows),
        "history": pd.DataFrame(history_rows),
    }
