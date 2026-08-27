"""六合彩固定球色的唯讀統計分析與展示資料。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ball_colours import COLOUR_HEX, COLOUR_KEYS, COLOUR_LABELS, COLOUR_MAPPING_VERSION, COLOUR_NUMBERS, COLOUR_SOURCE_URL, colour_counts, colour_for_number
from lotto_data import MAIN_COLUMNS


DEFAULT_WINDOWS = (10, 50)


def colour_draw_frame(draws: pd.DataFrame) -> pd.DataFrame:
    """衍生每一期正選及特別號的顏色資料；絕不改寫官方原始 CSV。"""
    rows: list[dict[str, Any]] = []
    for row in draws.itertuples(index=False):
        main_numbers = [int(getattr(row, column)) for column in MAIN_COLUMNS]
        counts = colour_counts(main_numbers)
        special = int(getattr(row, "Special"))
        rows.append(
            {
                "期數": int(getattr(row, "Draw")),
                "日期": pd.Timestamp(getattr(row, "Date")),
                "紅色": counts["red"],
                "藍色": counts["blue"],
                "綠色": counts["green"],
                "正選球色組成": "、".join(f"{COLOUR_LABELS[colour]} {counts[colour]}" for colour in COLOUR_KEYS),
                "特別號": special,
                "特別號球色": COLOUR_LABELS[colour_for_number(special)],
            }
        )
    return pd.DataFrame(rows)


def _summary_rows(frame: pd.DataFrame, *, scope: str) -> list[dict[str, Any]]:
    draw_count = len(frame)
    total_main_numbers = draw_count * 6
    rows: list[dict[str, Any]] = []
    for colour in COLOUR_KEYS:
        observed = int(frame[COLOUR_LABELS[colour]].sum()) if draw_count else 0
        expected = total_main_numbers * len(COLOUR_NUMBERS[colour]) / 49
        rows.append(
            {
                "範圍": scope,
                "球色": COLOUR_LABELS[colour],
                "正選實際球數": observed,
                "隨機期望球數": round(expected, 2),
                "實際比例": round(observed / total_main_numbers, 6) if total_main_numbers else 0.0,
                "固定球池比例": round(len(COLOUR_NUMBERS[colour]) / 49, 6),
                "與期望差異": round(observed - expected, 2),
                "球色鍵": colour,
                "球色代碼": COLOUR_HEX[colour],
            }
        )
    return rows


def build_colour_analysis(draws: pd.DataFrame, windows: tuple[int, ...] = DEFAULT_WINDOWS) -> dict[str, Any]:
    """建立整體、近期窗口及最近期數的球色研究狀態。

    此處的期望值來自在固定 49 個球中均勻抽取六個正選的描述性基準；球色為
    號碼的既定標籤，統計差異不可被詮釋為未來攪珠預測能力。
    """
    per_draw = colour_draw_frame(draws)
    overall_rows = _summary_rows(per_draw, scope=f"全期數（{len(per_draw):,} 期）")
    window_rows: list[dict[str, Any]] = []
    for window in windows:
        available = min(int(window), len(per_draw))
        if available <= 0:
            continue
        window_rows.extend(_summary_rows(per_draw.tail(available), scope=f"最近 {available} 期"))
    latest = per_draw.iloc[-1].to_dict() if not per_draw.empty else {}
    recent_limit = min(30, len(per_draw))
    recent = per_draw.tail(recent_limit).copy()
    trend = recent.loc[:, ["期數", "紅色", "藍色", "綠色"]].melt(id_vars="期數", var_name="球色", value_name="正選球數")
    return {
        "mapping_version": COLOUR_MAPPING_VERSION,
        "source_url": COLOUR_SOURCE_URL,
        "group_sizes": {COLOUR_LABELS[colour]: len(COLOUR_NUMBERS[colour]) for colour in COLOUR_KEYS},
        "draw_count": len(per_draw),
        "overall_table": pd.DataFrame(overall_rows),
        "window_table": pd.DataFrame(window_rows),
        "recent_draws": recent.sort_values("期數", ascending=False).reset_index(drop=True),
        "trend": trend,
        "latest_draw": latest,
    }


def colour_analysis_payload(draws: pd.DataFrame) -> dict[str, Any]:
    """將球色研究轉為可安全儲存在最新預測 JSON 的基本型別快照。"""
    state = build_colour_analysis(draws)
    latest = state["latest_draw"]
    return {
        "mapping_version": state["mapping_version"],
        "source_url": state["source_url"],
        "mapping_group_sizes": state["group_sizes"],
        "interpretation": "球色是固定號碼標籤；此摘要只作描述性統計，不加入正式機率、盲測或權重治理。",
        "latest_official_draw": {
            "draw": int(latest["期數"]) if latest else None,
            "date": pd.Timestamp(latest["日期"]).date().isoformat() if latest else None,
            "main_colour_counts": {colour: int(latest[COLOUR_LABELS[colour]]) for colour in COLOUR_KEYS} if latest else {},
            "main_colour_composition": str(latest.get("正選球色組成", "未提供")),
            "special_colour": str(latest.get("特別號球色", "未提供")),
        },
        "overall": state["overall_table"].drop(columns=["球色鍵", "球色代碼"], errors="ignore").to_dict(orient="records"),
        "recent_windows": state["window_table"].drop(columns=["球色鍵", "球色代碼"], errors="ignore").to_dict(orient="records"),
    }


def recommendation_colour_metadata(numbers: list[int], special_number: int | None = None) -> dict[str, Any]:
    """提供推薦組合的顏色資料；不產生或改變機率分數。"""
    numeric_numbers = [int(number) for number in numbers]
    metadata: dict[str, Any] = {
        "number_colours": [colour_for_number(number) for number in numeric_numbers],
        "main_colour_counts": colour_counts(numeric_numbers),
        "main_colour_composition": "、".join(
            f"{COLOUR_LABELS[colour]} {colour_counts(numeric_numbers)[colour]}" for colour in COLOUR_KEYS
        ),
    }
    if special_number is not None:
        metadata["special_number_colour"] = colour_for_number(int(special_number))
    return metadata
