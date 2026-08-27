"""預測組合版本保存、實際結果比對與命中率統計工具。"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from colour_analysis import recommendation_colour_metadata
from lotto_data import MAIN_COLUMNS, REQUIRED_COLUMNS, ValidationResult, validate_lotto_dataframe


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PREDICTION_HISTORY_PATH = PROJECT_ROOT / "data" / "prediction_history.json"
PREDICTION_HISTORY_SCHEMA_VERSION = 2
DRAW_DAYS = {1, 3, 5}  # Tuesday, Thursday, Saturday


def next_scheduled_draw_date(source_date: str | date | pd.Timestamp) -> str:
    """依一般周二、四、六攪珠節奏估計下一個目標日；實際安排以官方公告為準。"""
    current = pd.Timestamp(source_date).date()
    for offset in range(1, 8):
        candidate = current + timedelta(days=offset)
        if candidate.weekday() in DRAW_DAYS:
            return candidate.isoformat()
    raise RuntimeError("無法推算下一個攪珠日期。")


def load_prediction_history(path: Path = DEFAULT_PREDICTION_HISTORY_PATH) -> list[dict[str, Any]]:
    """讀取版本控制的預測紀錄；不存在或結構不正確時安全回傳空清單。"""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("predictions", [])
        if not isinstance(records, list):
            return []
        return [record for record in records if isinstance(record, dict)]
    except (OSError, json.JSONDecodeError):
        return []


def _write_prediction_history(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": PREDICTION_HISTORY_SCHEMA_VERSION,
        "purpose": "預測紀錄僅供統計教育與回測分析，無法可靠預測真實開獎結果。",
        "predictions": sorted(records, key=lambda record: (int(record["target_draw"]), record["generated_at_utc"])),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_prediction_record(
    history: pd.DataFrame,
    source_draw: int,
    source_date: str,
    model_payload: dict[str, Any],
) -> dict[str, Any]:
    """將五組組合連同可重現的來源資料範圍寫成下一期的唯一紀錄。"""
    combinations = model_payload.get("top_5_recommendations", [])
    normalized_combinations = []
    for item in combinations:
        set_index = int(item.get("set_index", len(normalized_combinations) + 1))
        numbers = sorted(int(number) for number in item.get("numbers", []))
        if len(numbers) != 6 or len(set(numbers)) != 6:
            raise ValueError("預測組合必須包含 6 個不重複號碼。")
        normalized = {
            "set_index": set_index,
            "numbers": numbers,
            "odd_count": int(item.get("odd_count", sum(number % 2 for number in numbers))),
            "number_sum": int(item.get("number_sum", sum(numbers))),
            "consecutive_pairs": int(
                item.get("consecutive_pairs", sum(right == left + 1 for left, right in zip(numbers, numbers[1:])))
            ),
        }
        try:
            strength_score = float(item.get("strength_score"))
            relative_strength_percent = int(item.get("relative_strength_percent"))
        except (TypeError, ValueError):
            strength_score = None
            relative_strength_percent = None
        if strength_score is not None and relative_strength_percent is not None and 0 <= relative_strength_percent <= 100:
            normalized["strength_score"] = round(strength_score, 6)
            normalized["relative_strength_percent"] = relative_strength_percent
            normalized["strength_label"] = str(item.get("strength_label", f"相對推薦強度 {relative_strength_percent}%"))
        if set_index == 1:
            try:
                special_number = int(item.get("special_number"))
            except (TypeError, ValueError) as error:
                raise ValueError("第一組 6+1 推薦組合必須包含研究用特別號碼。") from error
            if not 1 <= special_number <= 49 or special_number in numbers:
                raise ValueError("第一組研究用特別號碼必須介乎 1 至 49 且不可與六個主號重複。")
            normalized["recommendation_format"] = "6+1"
            normalized["special_number"] = special_number
        elif item.get("special_number") is not None:
            raise ValueError("只有第一組可以包含研究用特別號碼。")
        else:
            normalized["recommendation_format"] = "6"
        normalized.update(recommendation_colour_metadata(numbers, normalized.get("special_number")))
        normalized_combinations.append(normalized)
    if len(normalized_combinations) != 5 or {item["set_index"] for item in normalized_combinations} != {1, 2, 3, 4, 5}:
        raise ValueError("每次預測必須保存 5 組組合。")
    model = model_payload.get("model", {})
    return {
        "target_draw": int(source_draw) + 1,
        "target_date": next_scheduled_draw_date(source_date),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_history_records": int(len(history)),
        "source_latest_draw": int(source_draw),
        "source_latest_date": pd.Timestamp(source_date).date().isoformat(),
        "model": {
            "name": model.get("name", "未標示模型"),
            "features": model.get("features", []),
            "fusion": model.get("fusion", {}),
            "kmeans_clusters": model.get("kmeans_clusters"),
            "research_context": model.get("research_context", {}),
        },
        "combinations": normalized_combinations,
    }


def record_prediction(
    history: pd.DataFrame,
    source_draw: int,
    source_date: str,
    model_payload: dict[str, Any],
    path: Path = DEFAULT_PREDICTION_HISTORY_PATH,
) -> tuple[dict[str, Any], bool]:
    """為每個目標期數保存一筆不可覆寫的預測；同一期重跑時使用既有版本。"""
    record = build_prediction_record(history, source_draw, source_date, model_payload)
    records = load_prediction_history(path)
    for existing in records:
        if int(existing.get("target_draw", -1)) == record["target_draw"]:
            return existing, False
    records.append(record)
    _write_prediction_history(records, path)
    return record, True


def _formatted_numbers(numbers: list[int], hits: set[int] | None = None) -> str:
    hit_set = hits or set()
    return " · ".join(f"✅{number:02d}" if number in hit_set else f"{number:02d}" for number in numbers)


def build_hit_rate_table(
    draws: pd.DataFrame,
    records: list[dict[str, Any]],
) -> tuple[pd.DataFrame, ValidationResult | None]:
    """比對已結算目標期與實際六個正選；未結算預測保留為待攪珠狀態。"""
    validation = validate_lotto_dataframe(draws.loc[:, REQUIRED_COLUMNS].copy())
    if not validation.is_valid:
        return pd.DataFrame(), validation
    actual_by_draw = validation.data.set_index("Draw")
    rows = []
    for record in sorted(records, key=lambda item: int(item.get("target_draw", -1)), reverse=True):
        target_draw = int(record.get("target_draw", -1))
        combinations = record.get("combinations", [])
        actual_row = actual_by_draw.loc[target_draw] if target_draw in actual_by_draw.index else None
        combination_text = []
        hit_text = []
        hit_counts = []
        if actual_row is not None:
            actual_numbers = [int(actual_row[column]) for column in MAIN_COLUMNS]
            actual_set = set(actual_numbers)
            actual_text = _formatted_numbers(actual_numbers)
            special_text = f"{int(actual_row['Special']):02d}"
            status = "已結算"
            actual_date = pd.Timestamp(actual_row["Date"]).date().isoformat()
        else:
            actual_set = set()
            actual_text = "待攪珠"
            special_text = "—"
            status = "待攪珠"
            actual_date = "—"
        for combination in combinations:
            numbers = [int(number) for number in combination.get("numbers", [])]
            hits = set(numbers) & actual_set
            set_index = int(combination.get("set_index", len(combination_text) + 1))
            special_number = combination.get("special_number") if set_index == 1 else None
            special_suffix = ""
            if special_number is not None:
                special_value = int(special_number)
                special_suffix = f" + [特別號碼：{special_value:02d}]"
            label = f"組{set_index}（6+1）" if special_number is not None else f"組{set_index}"
            combination_text.append(f"{label}：" + _formatted_numbers(numbers) + special_suffix)
            hit_text.append(f"組{set_index}：" + (_formatted_numbers(sorted(hits), hits) if hits else "—"))
            hit_counts.append(len(hits))
        rows.append(
            {
                "期數": target_draw,
                "目標日期": record.get("target_date", "—"),
                "實際日期": actual_date,
                "狀態": status,
                "實際開獎號碼": actual_text,
                "特別號": special_text,
                "AI 預測 5 組組合": "\n".join(combination_text),
                "命中號碼": "\n".join(hit_text),
                "單期最高命中": max(hit_counts, default=0) if status == "已結算" else None,
                "五組合計命中": sum(hit_counts) if status == "已結算" else None,
                "每組命中數": " / ".join(map(str, hit_counts)) if status == "已結算" else "待結果",
            }
        )
    return pd.DataFrame(rows), None


def hit_rate_metrics(table: pd.DataFrame) -> dict[str, float | int]:
    """只以已結算預測計算平均最高命中與 3 個字以上次數。"""
    if table.empty or "狀態" not in table:
        return {"settled_draws": 0, "pending_draws": 0, "average_best_hits": 0.0, "draws_with_3_plus": 0, "average_total_hits": 0.0}
    settled = table.loc[table["狀態"] == "已結算"].copy()
    pending = int((table["狀態"] == "待攪珠").sum())
    if settled.empty:
        return {"settled_draws": 0, "pending_draws": pending, "average_best_hits": 0.0, "draws_with_3_plus": 0, "average_total_hits": 0.0}
    return {
        "settled_draws": int(len(settled)),
        "pending_draws": pending,
        "average_best_hits": float(settled["單期最高命中"].astype(float).mean()),
        "draws_with_3_plus": int((settled["單期最高命中"].astype(int) >= 3).sum()),
        "average_total_hits": float(settled["五組合計命中"].astype(float).mean()),
    }
