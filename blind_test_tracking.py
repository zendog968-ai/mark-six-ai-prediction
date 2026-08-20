"""Pre-registered, append-only blind-test tracking for Mark Six research."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lotto_data import MAIN_COLUMNS, REQUIRED_COLUMNS, train_fusion_model, validate_lotto_dataframe
from prediction_tracking import next_scheduled_draw_date


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_BLIND_TEST_HISTORY_PATH = PROJECT_ROOT / "data" / "blind_test_history.json"
BLIND_TEST_SCHEMA_VERSION = 1
BLIND_TEST_CONFIG_VERSION = "2026-08-20-v1"
HOT_COLD_POOL_SIZE = 16
BLIND_TEST_CONFIGS = (
    {
        "key": "fusion_top6",
        "label": "融合模型 Top-6（基準）",
        "rule": "依原有 Random Forest + XGBoost 等權融合分數取前 6 個號碼。",
    },
    {
        "key": "frequency50_50",
        "label": "50% frequency_50 變體",
        "rule": "0.5 × 標準化融合分數 + 0.5 × 標準化近 50 期頻率，取前 6 個號碼。",
    },
    {
        "key": "hot6",
        "label": "熱門 6 配置",
        "rule": "先以近 50 期頻率最高的 16 個號碼建立熱門池，再按融合分數取前 6 個號碼。",
    },
)


def _stable_minmax(values: np.ndarray) -> np.ndarray:
    numeric = values.astype(float)
    spread = float(numeric.max() - numeric.min())
    if spread == 0:
        return np.zeros_like(numeric, dtype=float)
    return (numeric - numeric.min()) / spread


def _source_history_hash(history: pd.DataFrame) -> str:
    canonical = history.loc[:, REQUIRED_COLUMNS].copy()
    canonical["Date"] = pd.to_datetime(canonical["Date"]).dt.date.astype(str)
    serialized = canonical.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _record_hash(record: dict[str, Any]) -> str:
    mutable_copy = {key: value for key, value in record.items() if key != "record_sha256"}
    serialized = json.dumps(mutable_copy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_numbers(numbers: list[int]) -> list[int]:
    normalized = sorted(int(number) for number in numbers)
    if len(normalized) != 6 or len(set(normalized)) != 6 or any(number < 1 or number > 49 for number in normalized):
        raise ValueError("每個盲測配置必須包含 6 個不重複且介於 1–49 的號碼。")
    return normalized


def _hot_pool(details: pd.DataFrame) -> list[int]:
    ordered = details.sort_values(
        ["frequency_50", "frequency_10", "gap", "number"],
        ascending=[False, False, True, True],
        kind="stable",
    )
    return ordered.head(HOT_COLD_POOL_SIZE)["number"].astype(int).tolist()


def build_blind_test_record(history: pd.DataFrame, source_draw: int, source_date: str) -> dict[str, Any]:
    """Build a single immutable record before the next draw outcome is available."""
    validation = validate_lotto_dataframe(history.loc[:, REQUIRED_COLUMNS].copy())
    if not validation.is_valid:
        raise ValueError("歷史資料未通過驗證：" + "；".join(validation.errors))
    validated_history = validation.data
    ranked, details, error = train_fusion_model(validated_history)
    if error or ranked is None or details is None:
        raise ValueError(error or "無法建立融合模型盲測候選。")

    ordered = details.sort_values("number", ignore_index=True)
    fusion_scores = ordered["fused_score"].to_numpy(dtype=float)
    frequency_scores = ordered["frequency_50"].to_numpy(dtype=float)
    frequency50_scores = 0.5 * _stable_minmax(fusion_scores) + 0.5 * _stable_minmax(frequency_scores)
    number_values = ordered["number"].to_numpy(dtype=int)
    fusion_top6 = details.sort_values(["fused_score", "number"], ascending=[False, True], kind="stable").head(6)["number"].astype(int).tolist()
    frequency50_top6 = number_values[np.argsort(-frequency50_scores, kind="stable")[:6]].tolist()
    hot_pool = _hot_pool(details)
    hot6 = (
        details[details["number"].isin(hot_pool)]
        .sort_values(["fused_score", "number"], ascending=[False, True], kind="stable")
        .head(6)["number"]
        .astype(int)
        .tolist()
    )
    candidates = {
        "fusion_top6": fusion_top6,
        "frequency50_50": frequency50_top6,
        "hot6": hot6,
    }
    variants = []
    for config in BLIND_TEST_CONFIGS:
        numbers = _validate_numbers(candidates[config["key"]])
        variants.append({**config, "numbers": numbers})

    record: dict[str, Any] = {
        "experiment_id": "marksix_three_config_blind_test",
        "schema_version": BLIND_TEST_SCHEMA_VERSION,
        "config_version": BLIND_TEST_CONFIG_VERSION,
        "target_draw": int(source_draw) + 1,
        "target_date": next_scheduled_draw_date(source_date),
        "locked_at_utc": datetime.now(UTC).isoformat(),
        "source_latest_draw": int(source_draw),
        "source_latest_date": pd.Timestamp(source_date).date().isoformat(),
        "source_history_records": int(len(validated_history)),
        "source_history_sha256": _source_history_hash(validated_history),
        "model": {
            "name": "Random Forest + XGBoost Ensemble",
            "fusion": {"random_forest_weight": 0.5, "xgboost_weight": 0.5},
            "features": ["frequency_50", "frequency_10", "gap", "kmeans_cluster"],
            "kmeans_clusters": int(details["kmeans_cluster"].nunique()),
        },
        "variants": variants,
        "status": "locked_pending_result",
        "purpose": "盲測僅供統計教育及模型評估；所有候選會在開獎前鎖定，不構成投注建議或中獎保證。",
    }
    record["record_sha256"] = _record_hash(record)
    return record


def load_blind_test_history(path: Path = DEFAULT_BLIND_TEST_HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("blind_tests", [])
        return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_blind_test_history(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": BLIND_TEST_SCHEMA_VERSION,
        "experiment_id": "marksix_three_config_blind_test",
        "config_version": BLIND_TEST_CONFIG_VERSION,
        "purpose": "預先鎖定三種固定配置，待實際主號結果可用時才進行比對；不得用於投注決策。",
        "blind_tests": sorted(records, key=lambda record: (int(record["target_draw"]), record["locked_at_utc"])),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def record_blind_test(
    history: pd.DataFrame,
    source_draw: int,
    source_date: str,
    path: Path = DEFAULT_BLIND_TEST_HISTORY_PATH,
) -> tuple[dict[str, Any], bool]:
    """Append exactly one locked record per target draw; never replace an existing record."""
    proposed = build_blind_test_record(history, source_draw, source_date)
    records = load_blind_test_history(path)
    for existing in records:
        if int(existing.get("target_draw", -1)) != proposed["target_draw"]:
            continue
        if existing.get("record_sha256") != _record_hash(existing):
            raise ValueError(f"盲測期數 {proposed['target_draw']} 的既有紀錄雜湊不符，拒絕覆寫。")
        if existing.get("config_version") != BLIND_TEST_CONFIG_VERSION:
            raise ValueError(f"盲測期數 {proposed['target_draw']} 已以另一套配置鎖定，拒絕覆寫。")
        return existing, False
    records.append(proposed)
    _write_blind_test_history(records, path)
    return proposed, True


def build_blind_test_table(draws: pd.DataFrame, records: list[dict[str, Any]]) -> tuple[pd.DataFrame, Any | None]:
    validation = validate_lotto_dataframe(draws.loc[:, REQUIRED_COLUMNS].copy())
    if not validation.is_valid:
        return pd.DataFrame(), validation
    actual_by_draw = validation.data.set_index("Draw")
    rows = []
    for record in sorted(records, key=lambda item: int(item.get("target_draw", -1)), reverse=True):
        target_draw = int(record.get("target_draw", -1))
        is_intact = record.get("record_sha256") == _record_hash(record)
        actual_row = actual_by_draw.loc[target_draw] if target_draw in actual_by_draw.index else None
        actual_numbers = [int(actual_row[column]) for column in MAIN_COLUMNS] if actual_row is not None else []
        actual_set = set(actual_numbers)
        for variant in record.get("variants", []):
            numbers = [int(number) for number in variant.get("numbers", [])]
            hits = sorted(set(numbers) & actual_set)
            settled = actual_row is not None
            rows.append(
                {
                    "期數": target_draw,
                    "目標日期": record.get("target_date", "—"),
                    "配置": variant.get("label", variant.get("key", "未標示")),
                    "候選號碼": " · ".join(f"{number:02d}" for number in numbers),
                    "狀態": "已結算" if settled else "已鎖定待攪珠",
                    "實際正選": " · ".join(f"{number:02d}" for number in actual_numbers) if settled else "待攪珠",
                    "命中號碼": " · ".join(f"✅{number:02d}" for number in hits) if settled and hits else "—",
                    "命中數": len(hits) if settled else None,
                    "鎖定時間（UTC）": record.get("locked_at_utc", "—"),
                    "紀錄完整性": "通過" if is_intact else "雜湊不符",
                }
            )
    return pd.DataFrame(rows), None


def blind_test_metrics(table: pd.DataFrame) -> dict[str, float | int]:
    if table.empty:
        return {"locked_records": 0, "settled_records": 0, "settled_variants": 0, "average_hits": 0.0, "three_plus": 0}
    settled = table.loc[table["狀態"] == "已結算"].copy()
    unique_targets = int(table["期數"].nunique())
    settled_targets = int(settled["期數"].nunique()) if not settled.empty else 0
    return {
        "locked_records": unique_targets,
        "settled_records": settled_targets,
        "settled_variants": int(len(settled)),
        "average_hits": float(settled["命中數"].astype(float).mean()) if not settled.empty else 0.0,
        "three_plus": int((settled["命中數"].astype(int) >= 3).sum()) if not settled.empty else 0,
    }
