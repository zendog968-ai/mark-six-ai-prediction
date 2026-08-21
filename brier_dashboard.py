"""Data layer for the four-configuration Brier inference dashboard.

Only complete, pre-locked 49-number probability vectors joined to official
six-main-number outcomes can enter a Brier or inference calculation.  The
module intentionally returns empty outputs rather than inventing history.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from brier_significance import brier_score_per_draw, compare_configurations


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_BRIER_TRACKING_PATH = PROJECT_ROOT / "data" / "brier_tracking_history.json"
DEFAULT_MULTISCALE_PREVIEW_PATH = PROJECT_ROOT / "data" / "multiscale_research_preview.json"
BASELINE_KEY = "fusion_top6"
CONFIGURATIONS = (
    ("fusion_top6", "融合模型 Top-6（基準）"),
    ("frequency50_50", "50% frequency_50 變體"),
    ("hot6", "熱門 6 配置"),
    ("multiscale_calibrated", "多尺度校準（研究配置）"),
)
CONFIG_LABELS = dict(CONFIGURATIONS)


def load_brier_tracking(path: Path = DEFAULT_BRIER_TRACKING_PATH) -> list[dict[str, Any]]:
    """Load the append-only Brier tracking payload, returning no records on read errors."""
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def load_multiscale_preview(path: Path = DEFAULT_MULTISCALE_PREVIEW_PATH) -> dict[str, Any] | None:
    """Read an optional research-only preview without treating it as blind-test evidence."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def build_brier_by_draw(records: Iterable[dict[str, Any]], settlement_history: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Build one row per fully settled common draw, excluding incomplete records.

    Each accepted record must contain ``actual_main_numbers`` and a
    ``configuration_probabilities`` mapping with exactly four 49-number vectors.
    Vectors are not inferred from Top-6 candidates because that would fabricate
    probability forecasts retroactively.
    """
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    expected_keys = list(CONFIG_LABELS)
    actual_by_draw = {}
    if settlement_history is not None and not settlement_history.empty:
        actual_by_draw = {
            int(row.Draw): [int(row.N1), int(row.N2), int(row.N3), int(row.N4), int(row.N5), int(row.N6)]
            for row in settlement_history.itertuples(index=False)
        }
    for record in records:
        draw = record.get("target_draw")
        actual = record.get("actual_main_numbers") or actual_by_draw.get(int(draw), []) if isinstance(draw, int) else []
        probability_map = record.get("configuration_probabilities")
        if not isinstance(draw, int) or not isinstance(probability_map, dict):
            continue
        if not isinstance(actual, list) or len(actual) != 6:
            warnings.append(f"期數 {draw} 已鎖定完整機率向量，正在等待官方正選結果結算。")
            continue
        missing = [key for key in expected_keys if key not in probability_map]
        if missing:
            warnings.append(f"期數 {draw} 缺少共同配置的完整機率向量，未納入 Brier 比較。")
            continue
        try:
            row: dict[str, Any] = {
                "Draw": draw,
                "Date": record.get("target_date", "—"),
                "實際正選": " · ".join(f"{int(number):02d}" for number in sorted(actual)),
            }
            for key in expected_keys:
                vector = np.asarray(probability_map[key], dtype=float)
                row[key] = float(brier_score_per_draw(vector.reshape(1, 49), [actual])[0])
            rows.append(row)
        except (TypeError, ValueError) as error:
            warnings.append(f"期數 {draw} 的機率向量無效，未納入比較：{error}")
    if not rows:
        return pd.DataFrame(columns=["Draw", "Date", "實際正選", *expected_keys]), warnings
    frame = pd.DataFrame(rows).sort_values("Draw").drop_duplicates("Draw", keep="last").reset_index(drop=True)
    return frame, warnings


def brier_coverage_summary(
    frame: pd.DataFrame,
    locked_three_config_records: int,
    multiscale_preview: dict[str, Any] | None,
    locked_four_config_records: int = 0,
) -> pd.DataFrame:
    """Summarise real Brier coverage without equating Top-6-only records to probabilities."""
    completed = int(len(frame))
    rows = []
    for key, label in CONFIGURATIONS:
        if completed:
            status = "已有共同已結算完整機率記錄"
        elif locked_four_config_records:
            status = "完整 49 號機率已鎖定，待官方結果結算"
        elif key == "multiscale_calibrated" and multiscale_preview is not None:
            status = "研究預覽已建立，尚未納入正式四配置盲測"
        elif key != "multiscale_calibrated" and locked_three_config_records:
            status = "已有鎖定 Top-6 紀錄，但未保存完整 49 號機率向量"
        else:
            status = "尚未建立可結算的完整機率紀錄"
        rows.append({"配置": label, "完整已結算 Brier 期數": completed, "追蹤狀態": status})
    return pd.DataFrame(rows)


def cumulative_brier(frame: pd.DataFrame) -> pd.DataFrame:
    """Return tidy cumulative mean Brier values for charting."""
    if frame.empty:
        return pd.DataFrame(columns=["期數", "配置", "累積平均 Brier"])
    rows = []
    for key, label in CONFIGURATIONS:
        running = frame[key].expanding().mean()
        rows.extend(
            {"期數": int(draw), "配置": label, "累積平均 Brier": float(value)}
            for draw, value in zip(frame["Draw"], running, strict=True)
        )
    return pd.DataFrame(rows)


def run_four_configuration_inference(
    frame: pd.DataFrame,
    *,
    block_length: int,
    n_bootstrap: int,
) -> tuple[pd.DataFrame, str | None]:
    """Run descriptive four-configuration inference only on common settled records."""
    if len(frame) < 3:
        return pd.DataFrame(), "共同已結算完整機率期數少於 3，尚不可執行 Bootstrap 或 Diebold–Mariano 檢定。"
    try:
        results = compare_configurations(
            frame.loc[:, ["Draw", *CONFIG_LABELS]],
            baseline=BASELINE_KEY,
            candidates=[key for key in CONFIG_LABELS if key != BASELINE_KEY],
            block_length=min(block_length, len(frame)),
            n_bootstrap=n_bootstrap,
        )
    except ValueError as error:
        return pd.DataFrame(), str(error)
    results["配置"] = results["configuration"].map(CONFIG_LABELS)
    return results, None
