"""Data shaping for the read-only 5/10 draw window research dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_LONG_WINDOW_RESEARCH_PATH = (
    Path(__file__).resolve().parent / "data" / "long_window_research_snapshot.json"
)


def _p_value(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 0.0001:
        return f"{value:.2e}"
    return f"{value:.4f}"


def _count(values: list[dict[str, Any]]) -> int:
    return len(values) if isinstance(values, list) else 0


def load_long_window_research(path: Path = DEFAULT_LONG_WINDOW_RESEARCH_PATH) -> dict[str, Any] | None:
    """Load the versioned long-window research snapshot, or return None safely."""
    if not path.exists():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _build_chart_tables(
    family_table: pd.DataFrame,
    holdout_table: pd.DataFrame,
    frequency_detail_table: pd.DataFrame,
    window_score_table: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Build the three dashboard chart tables from a possibly filtered state."""
    window_signal_chart = pd.DataFrame(
        [
            {
                "窗口": f"{window} 期",
                "全樣本 Holm 候選": int(family_table[f"{window}期 Holm 顯著數"].sum()),
                "留出驗證通過": int(
                    (holdout_table.loc[holdout_table["窗口"] == f"{window} 期", "通過留出驗證"] == "是").sum()
                ),
            }
            for window in ("5", "10")
        ]
    ).set_index("窗口")
    frequency_chart = family_table.set_index("組合家族")[
        ["總頻率原始偏離數", "總頻率 Holm 顯著數"]
    ]
    holdout_flow_chart = pd.DataFrame(
        [
            {
                "窗口": f"{window} 期",
                "探索期候選": int((holdout_table["窗口"] == f"{window} 期").sum()),
                "通過留出驗證": int(
                    (holdout_table.loc[holdout_table["窗口"] == f"{window} 期", "通過留出驗證"] == "是").sum()
                ),
            }
            for window in ("5", "10")
        ]
    ).set_index("窗口")
    frequency_tooltip_chart = pd.concat(
        [
            frequency_detail_table.assign(
                數據系列="實際出現期數",
                期數=lambda table: table["實際出現期數"],
            ),
            frequency_detail_table.assign(
                數據系列="隨機期望期數",
                期數=lambda table: table["隨機期望期數"],
            ),
        ],
        ignore_index=True,
    )
    window_tooltip_chart = pd.concat(
        [
            window_score_table.assign(
                數據系列="實際窗口分數",
                分數=lambda table: table["實際窗口分數"],
            ),
            window_score_table.assign(
                數據系列="隨機期望分數",
                分數=lambda table: table["隨機期望分數"],
            ),
        ],
        ignore_index=True,
    )
    return {
        "window_signal_chart": window_signal_chart,
        "frequency_chart": frequency_chart,
        "holdout_flow_chart": holdout_flow_chart,
        "frequency_tooltip_chart": frequency_tooltip_chart,
        "window_tooltip_chart": window_tooltip_chart,
    }


def filter_long_window_research(state: dict[str, Any], selected_families: list[str]) -> dict[str, Any]:
    """Return a display state restricted to the requested predefined families."""
    if not state.get("available"):
        return state

    selected = set(selected_families)
    family_table = state["family_table"].loc[
        state["family_table"]["組合家族"].isin(selected)
    ].copy()
    holdout_table = state["holdout_table"].loc[
        state["holdout_table"]["組合家族"].isin(selected)
    ].copy()
    frequency_detail_table = state["frequency_detail_table"].loc[
        state["frequency_detail_table"]["組合家族"].isin(selected)
    ].copy()
    window_score_table = state["window_score_table"].loc[
        state["window_score_table"]["組合家族"].isin(selected)
    ].copy()
    charts = _build_chart_tables(
        family_table,
        holdout_table,
        frequency_detail_table,
        window_score_table,
    )
    filtered = dict(state)
    filtered.update(charts)
    filtered["family_table"] = family_table
    filtered["holdout_table"] = holdout_table
    filtered["frequency_detail_table"] = frequency_detail_table
    filtered["window_score_table"] = window_score_table
    filtered["total_tests"] = int(family_table["同時檢驗數"].sum())
    filtered["initial_signals"] = {
        window: int(family_table[f"{window}期 Holm 顯著數"].sum())
        for window in ("5", "10")
    }
    filtered["passed_holdout"] = int((holdout_table["通過留出驗證"] == "是").sum())
    return filtered


def build_long_window_research_state(path: Path = DEFAULT_LONG_WINDOW_RESEARCH_PATH) -> dict[str, Any]:
    """Convert the long-window analysis snapshot into Streamlit-ready tables."""
    raw = load_long_window_research(path)
    if raw is None:
        return {"available": False, "message": "未找到可驗證的 5／10 期窗口研究快照。"}

    method = raw.get("method", {})
    families = raw.get("families", {})
    if not isinstance(method, dict) or not isinstance(families, dict):
        return {"available": False, "message": "窗口研究快照格式不完整。"}

    family_rows: list[dict[str, Any]] = []
    frequency_detail_rows: list[dict[str, Any]] = []
    window_score_rows: list[dict[str, Any]] = []
    initial_signals = {"5": 0, "10": 0}
    total_tests = 0
    for family_name, family in families.items():
        if not isinstance(family, dict):
            continue
        tests = int(family.get("tests", 0))
        total_tests += tests
        windows = family.get("windows", {})
        row: dict[str, Any] = {
            "組合家族": family_name,
            "同時檢驗數": tests,
            "總頻率原始偏離數": _count(family.get("frequency_significant_unadjusted", [])),
            "總頻率 Holm 顯著數": _count(family.get("frequency_significant_holm", [])),
        }
        for window in ("5", "10"):
            values = windows.get(window, {}) if isinstance(windows, dict) else {}
            significant = values.get("significant", []) if isinstance(values, dict) else []
            top = (values.get("top_raw", []) or [{}])[0] if isinstance(values, dict) else {}
            initial_signals[window] += _count(significant)
            row[f"{window}期 Holm 顯著數"] = _count(significant)
            row[f"{window}期最突出候選"] = top.get("pattern", "—")
            top_window = top.get("windows", {}).get(window, {}) if isinstance(top, dict) else {}
            row[f"{window}期原始 p"] = _p_value(top_window.get("two_sided_p"))
            row[f"{window}期方向"] = top_window.get("interpretation", "—")
            if isinstance(top, dict) and top:
                window_score_rows.append(
                    {
                        "組合家族": family_name,
                        "窗口": f"{window} 期",
                        "候選模式": top.get("pattern", "—"),
                        "實際窗口分數": float(top_window.get("observed_score", 0.0)),
                        "隨機期望分數": float(top_window.get("expected_score", 0.0)),
                        "窗口偏離": float(top_window.get("observed_score", 0.0)) - float(top_window.get("expected_score", 0.0)),
                        "方向": top_window.get("interpretation", "—"),
                        "窗口原始 p": float(top_window.get("two_sided_p", 1.0)),
                        "窗口 Holm p": float(top_window.get("holm_adjusted_p_within_window", 1.0)),
                        "窗口 Holm 狀態": "通過" if top_window.get("significant_at_0_05") else "未通過",
                    }
                )
                if window == "5":
                    observed_draws = float(top.get("observed_draws", 0.0))
                    expected_draws = float(top.get("expected_draws", 0.0))
                    frequency_detail_rows.append(
                        {
                            "組合家族": family_name,
                            "候選模式": top.get("pattern", "—"),
                            "實際出現期數": observed_draws,
                            "隨機期望期數": expected_draws,
                            "頻率偏離": observed_draws - expected_draws,
                            "基準機率": float(top.get("baseline_probability", 0.0)),
                            "總頻率原始 p": float(top.get("frequency_two_sided_p", 1.0)),
                            "總頻率 Holm p": float(top.get("frequency_holm_adjusted_p", 1.0)),
                            "總頻率 Holm 狀態": "通過" if top.get("frequency_significant_at_0_05") else "未通過",
                        }
                    )
        family_rows.append(row)

    holdout = raw.get("temporal_holdout", {})
    holdout_rows: list[dict[str, Any]] = []
    passed_holdout = 0
    for candidate in holdout.get("candidates", []) if isinstance(holdout, dict) else []:
        source = candidate.get("selected_from", {})
        window = str(source.get("window", ""))
        values = candidate.get("windows", {}).get(window, {})
        passed = bool(values.get("significant_at_0_05"))
        passed_holdout += int(passed)
        holdout_rows.append(
            {
                "窗口": f"{window} 期",
                "組合家族": candidate.get("family", "—"),
                "探索期選出候選": candidate.get("pattern", "—"),
                "留出期方向": values.get("interpretation", "—"),
                "留出期原始 p": _p_value(values.get("two_sided_p")),
                "跨家族 Holm p": _p_value(values.get("holm_adjusted_p_across_selected_families")),
                "通過留出驗證": "是" if passed else "否",
            }
        )

    date_range = method.get("date_range", ["—", "—"])
    family_table = pd.DataFrame(family_rows)
    holdout_table = pd.DataFrame(holdout_rows)
    frequency_detail_table = pd.DataFrame(frequency_detail_rows)
    window_score_table = pd.DataFrame(window_score_rows)
    charts = _build_chart_tables(
        family_table,
        holdout_table,
        frequency_detail_table,
        window_score_table,
    )
    return {
        "available": True,
        "draw_count": int(method.get("draw_count", 0)),
        "date_range": date_range,
        "source_text": "、".join(method.get("sources", [])),
        "family_table": family_table,
        "holdout_table": holdout_table,
        "frequency_detail_table": frequency_detail_table,
        "window_score_table": window_score_table,
        **charts,
        "total_tests": total_tests,
        "initial_signals": initial_signals,
        "passed_holdout": passed_holdout,
        "training_draws": int(holdout.get("training_draws", 0)),
        "holdout_draws": int(holdout.get("holdout_draws", 0)),
        "method": method,
    }
