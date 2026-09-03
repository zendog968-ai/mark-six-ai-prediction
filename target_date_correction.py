from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from datetime import date
from typing import Any

TARGET_LOG_KEYS = ("prediction_log", "blind_test_log", "four_config_brier_log")


def correct_target_record(
    record: dict[str, Any],
    target_date: str | date,
    record_hash: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    """Return a copy with only target_date and, when present, its dependent hash changed."""
    corrected = deepcopy(record)
    corrected_date = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
    corrected["target_date"] = corrected_date
    if "record_sha256" in corrected:
        if record_hash is None:
            raise ValueError("record_hash is required when record_sha256 is present")
        corrected["record_sha256"] = record_hash(corrected)
    return corrected


def correct_prediction_payload(
    payload: dict[str, Any],
    target_draw: int,
    target_date: str | date,
) -> dict[str, Any]:
    """Return a copy with matching top-level and log target dates corrected."""
    corrected = deepcopy(payload)
    corrected_date = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
    if int(corrected.get("target_draw", -1)) == target_draw:
        corrected["target_date"] = corrected_date
    for key in TARGET_LOG_KEYS:
        section = corrected.get(key)
        if isinstance(section, dict) and int(section.get("target_draw", -1)) == target_draw:
            section["target_date"] = corrected_date
    return corrected
