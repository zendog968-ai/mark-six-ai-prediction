"""Append-only four-configuration probability records for Brier tracking.

This module is deliberately separate from the original Top-6-only blind-test
ledger. Every record stores full 49-number probability vectors before its
target draw is known, so later Brier scores can be derived from official
outcomes without reconstructing probabilities retrospectively.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from blind_test_tracking import _hot_pool, _stable_minmax
from lotto_data import MAIN_COLUMNS, REQUIRED_COLUMNS, train_fusion_model, validate_lotto_dataframe
from prediction_tracking import next_scheduled_draw_date


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_FOUR_CONFIG_HISTORY_PATH = PROJECT_ROOT / "data" / "brier_tracking_history.json"
DEFAULT_EXTENDED_HISTORY_PATH = PROJECT_ROOT / "data" / "lotto_history_extended_2002_2026.csv"
FOUR_CONFIG_VERSION = "2026-08-21-v1"
MULTISCALE_WINDOW = 200
MULTISCALE_CALIBRATION_DRAWS = 360
SEED = 20260820


def _canonical_history_hash(draws: pd.DataFrame) -> str:
    canonical = draws.loc[:, REQUIRED_COLUMNS].copy()
    canonical["Date"] = pd.to_datetime(canonical["Date"]).dt.date.astype(str)
    return hashlib.sha256(canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def _record_hash(record: dict[str, Any]) -> str:
    source = {key: value for key, value in record.items() if key != "record_sha256"}
    serialized = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _expected_six(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    if values.shape != (49,) or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("機率分數必須為 49 個非負有限數值。")
    if np.isclose(values.sum(), 0.0):
        values = np.ones(49, dtype=float)
    probabilities = values * (6.0 / float(values.sum()))
    if (probabilities > 1.0).any():
        raise ValueError("機率正規化後出現大於 1 的不合法數值。")
    return probabilities


def _multiscale_dataset(draws: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    matrix = draws.loc[:, MAIN_COLUMNS].to_numpy(dtype=int)
    if len(matrix) <= MULTISCALE_WINDOW + MULTISCALE_CALIBRATION_DRAWS:
        raise ValueError("擴充歷史資料不足以建立多尺度訓練與 360 期校準區段。")
    weights = np.exp(-np.log(2) * np.arange(MULTISCALE_WINDOW - 1, -1, -1) / 25.0)
    rows: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    groups: list[np.ndarray] = []
    values = np.arange(1, 50)
    for cutoff in range(MULTISCALE_WINDOW, len(draws)):
        history = matrix[:cutoff]
        recent_10, recent_50 = history[-10:], history[-50:]
        recent_100, recent_200 = history[-100:], history[-MULTISCALE_WINDOW:]
        frequency_10 = np.bincount(recent_10.ravel(), minlength=50)[1:]
        frequency_50 = np.bincount(recent_50.ravel(), minlength=50)[1:]
        frequency_100 = np.bincount(recent_100.ravel(), minlength=50)[1:]
        frequency_200 = np.bincount(recent_200.ravel(), minlength=50)[1:]
        per_draw_counts = (recent_200[:, :, None] == values[None, None, :]).sum(axis=1)
        decayed = (per_draw_counts * weights[:, None]).sum(axis=0)
        last_seen = np.full(49, -1, dtype=int)
        for index, numbers in enumerate(history):
            last_seen[numbers - 1] = index
        gap = np.minimum(cutoff - last_seen - 1, MULTISCALE_WINDOW)
        trend = frequency_10 / 10.0 - frequency_100 / 100.0
        rows.append(np.column_stack((frequency_50, frequency_10, frequency_100, frequency_200, gap, decayed, trend)).astype(np.float32))
        outcome = np.zeros(49, dtype=np.int8)
        outcome[matrix[cutoff] - 1] = 1
        labels.append(outcome)
        groups.append(np.full(49, cutoff, dtype=int))
    return np.vstack(rows), np.concatenate(labels), np.concatenate(groups)


def _next_multiscale_features(draws: pd.DataFrame) -> np.ndarray:
    matrix = draws.loc[:, MAIN_COLUMNS].to_numpy(dtype=int)
    history = matrix[-MULTISCALE_WINDOW:]
    values = np.arange(1, 50)
    frequency_10 = np.bincount(history[-10:].ravel(), minlength=50)[1:]
    frequency_50 = np.bincount(history[-50:].ravel(), minlength=50)[1:]
    frequency_100 = np.bincount(history[-100:].ravel(), minlength=50)[1:]
    frequency_200 = np.bincount(history.ravel(), minlength=50)[1:]
    weights = np.exp(-np.log(2) * np.arange(MULTISCALE_WINDOW - 1, -1, -1) / 25.0)
    per_draw_counts = (history[:, :, None] == values[None, None, :]).sum(axis=1)
    decayed = (per_draw_counts * weights[:, None]).sum(axis=0)
    last_seen = np.full(49, -1, dtype=int)
    for index, numbers in enumerate(matrix):
        last_seen[numbers - 1] = index
    gap = np.minimum(len(matrix) - last_seen - 1, MULTISCALE_WINDOW)
    trend = frequency_10 / 10.0 - frequency_100 / 100.0
    return np.column_stack((frequency_50, frequency_10, frequency_100, frequency_200, gap, decayed, trend)).astype(np.float32)


def _model_pair() -> tuple[RandomForestClassifier, XGBClassifier]:
    random_forest = RandomForestClassifier(
        n_estimators=100, min_samples_leaf=32, max_depth=8, class_weight="balanced_subsample", random_state=SEED + 1, n_jobs=-1
    )
    xgboost = XGBClassifier(
        n_estimators=100, max_depth=3, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9,
        objective="binary:logistic", eval_metric="logloss", scale_pos_weight=43.0 / 6.0, tree_method="hist", random_state=SEED + 1, n_jobs=1
    )
    return random_forest, xgboost


def _multiscale_probabilities(extended_history: pd.DataFrame) -> np.ndarray:
    features, labels, groups = _multiscale_dataset(extended_history)
    unique_groups = np.unique(groups)
    train_groups, calibration_groups = unique_groups[:-MULTISCALE_CALIBRATION_DRAWS], unique_groups[-MULTISCALE_CALIBRATION_DRAWS:]
    train_mask, calibration_mask = np.isin(groups, train_groups), np.isin(groups, calibration_groups)
    random_forest, xgboost = _model_pair()
    random_forest.fit(features[train_mask], labels[train_mask])
    xgboost.fit(features[train_mask], labels[train_mask])
    calibration_features = features[calibration_mask]
    calibration_scores = np.column_stack((random_forest.predict_proba(calibration_features)[:, 1], xgboost.predict_proba(calibration_features)[:, 1]))
    calibrator = LogisticRegression(C=0.05, max_iter=1000, random_state=SEED).fit(calibration_scores, labels[calibration_mask])
    next_features = _next_multiscale_features(extended_history)
    next_scores = np.column_stack((random_forest.predict_proba(next_features)[:, 1], xgboost.predict_proba(next_features)[:, 1]))
    return _expected_six(calibrator.predict_proba(next_scores)[:, 1])


def _vector_to_top6(probabilities: np.ndarray) -> list[int]:
    return sorted((np.argsort(-probabilities, kind="stable")[:6] + 1).astype(int).tolist())


def build_four_config_record(extended_history: pd.DataFrame, source_draw: int, source_date: str) -> dict[str, Any]:
    """Create a pre-result record containing all four complete probability vectors."""
    validation = validate_lotto_dataframe(extended_history.loc[:, REQUIRED_COLUMNS].copy())
    if not validation.is_valid:
        raise ValueError("擴充歷史資料未通過驗證：" + "；".join(validation.errors))
    draws = validation.data
    source = draws.iloc[-1]
    if int(source["Draw"]) != int(source_draw):
        raise ValueError("擴充歷史資料最新期數與每日更新結果不一致，拒絕鎖定四配置機率。")
    if pd.Timestamp(source["Date"]).date().isoformat() != pd.Timestamp(source_date).date().isoformat():
        raise ValueError("擴充歷史資料最新日期與每日更新結果不一致，拒絕鎖定四配置機率。")

    _ranked, details, error = train_fusion_model(draws)
    if error or details is None:
        raise ValueError(error or "無法建立融合模型完整機率向量。")
    ordered = details.sort_values("number", ignore_index=True)
    fusion = _expected_six(ordered["fused_score"].to_numpy(dtype=float))
    frequency50_scores = 0.5 * _stable_minmax(ordered["fused_score"].to_numpy(dtype=float)) + 0.5 * _stable_minmax(ordered["frequency_50"].to_numpy(dtype=float))
    frequency50 = _expected_six(frequency50_scores)
    hot_mask = np.isin(ordered["number"].to_numpy(dtype=int), _hot_pool(details))
    hot_scores = np.where(hot_mask, ordered["fused_score"].to_numpy(dtype=float), 0.0)
    hot6 = _expected_six(hot_scores)
    multiscale = _multiscale_probabilities(draws)
    probability_map = {
        "fusion_top6": fusion,
        "frequency50_50": frequency50,
        "hot6": hot6,
        "multiscale_calibrated": multiscale,
    }
    labels = {
        "fusion_top6": "融合模型 Top-6（基準）",
        "frequency50_50": "50% frequency_50 變體",
        "hot6": "熱門 6 配置",
        "multiscale_calibrated": "多尺度校準（研究配置）",
    }
    record: dict[str, Any] = {
        "experiment_id": "marksix_four_configuration_brier_tracking",
        "config_version": FOUR_CONFIG_VERSION,
        "target_draw": int(source_draw) + 1,
        "target_date": next_scheduled_draw_date(source_date),
        "locked_at_utc": datetime.now(UTC).isoformat(),
        "source_latest_draw": int(source_draw),
        "source_latest_date": pd.Timestamp(source_date).date().isoformat(),
        "source_history_records": int(len(draws)),
        "source_history_sha256": _canonical_history_hash(draws),
        "configuration_probabilities": {key: [round(float(value), 10) for value in values] for key, values in probability_map.items()},
        "variants": [{"key": key, "label": labels[key], "numbers": _vector_to_top6(values)} for key, values in probability_map.items()],
        "status": "locked_pending_result",
        "purpose": "四配置完整機率只用作開獎後 Brier、Bootstrap 與 Diebold–Mariano 統計研究；不得用於投注決策。",
    }
    record["record_sha256"] = _record_hash(record)
    return record


def load_four_config_history(path: Path = DEFAULT_FOUR_CONFIG_HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def record_four_config(
    extended_history: pd.DataFrame,
    source_draw: int,
    source_date: str,
    path: Path = DEFAULT_FOUR_CONFIG_HISTORY_PATH,
) -> tuple[dict[str, Any], bool]:
    """Append exactly one immutable four-configuration vector record per target draw."""
    target_draw = int(source_draw) + 1
    records = load_four_config_history(path)
    for existing in records:
        if int(existing.get("target_draw", -1)) != target_draw:
            continue
        if existing.get("record_sha256") != _record_hash(existing):
            raise ValueError(f"四配置盲測期數 {target_draw} 的既有紀錄雜湊不符，拒絕覆寫。")
        if existing.get("config_version") != FOUR_CONFIG_VERSION:
            raise ValueError(f"四配置盲測期數 {target_draw} 已以其他配置版本鎖定，拒絕覆寫。")
        return existing, False
    proposed = build_four_config_record(extended_history, source_draw, source_date)
    records.append(proposed)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "experiment_id": "marksix_four_configuration_brier_tracking",
        "config_version": FOUR_CONFIG_VERSION,
        "purpose": "只接受開獎前鎖定的完整 49 號機率向量；實際結果由官方歷史 CSV 動態結算。",
        "records": sorted(records, key=lambda record: (int(record["target_draw"]), record["locked_at_utc"])),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return proposed, True
