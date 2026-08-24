"""Data shaping for the read-only 5/10 draw window research dashboard."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_LONG_WINDOW_RESEARCH_PATH = (
    Path(__file__).resolve().parent / "data" / "long_window_research_snapshot.json"
)


RESEARCH_COPY = {
    "zh": {
        "language_label": "顯示語言",
        "language_help": "只改變窗口研究頁的文字、表格與圖表標籤；統計資料與檢定規則不變。",
        "title": "5／10 期窗口頻率研究",
        "intro": "本區展示已封存的長期真實資料研究快照；資料以均勻 49 選 6 為基準，並對同一組合家族作 Holm 多重比較校正。它不會修改模型、盲測紀錄或權重。",
        "family_filter": "組合家族篩選器",
        "family_filter_help": "篩選會同步套用至家族摘要、全樣本候選、總頻率與時間留出驗證圖表。清除全部選項可檢視空白狀態。",
        "sample": "研究樣本",
        "tests": "預先定義檢驗",
        "five_signals": "5 期全樣本候選",
        "holdout_passed": "留出驗證通過",
        "no_families": "尚未選擇組合家族。請在上方選擇至少一個家族以顯示研究表格與圖表。",
        "range": "資料範圍：{start} 至 {end}。所選家族中，全樣本的少數表面偏離在按時間保留的後 {holdout:,} 期均未通過驗證；因此不列為模型訊號。",
        "summary_title": "家族摘要：總頻率與窗口偏離",
        "signal_holdout_title": "5／10 期全樣本候選與留出驗證",
        "signal_holdout_caption": "長條僅代表通過家族內 Holm 校正的探索候選數；留出驗證通過數才是可追蹤的研究結果。",
        "frequency_title": "實際頻率與隨機期望：懸浮查看詳細數值",
        "frequency_caption": "游標移到長條可查看候選模式、實際期數、隨機期望、偏離及 Holm 校正資訊。所有候選均屬研究篩查，不構成預測訊號。",
        "window_title": "5／10 期窗口分數趨勢：懸浮查看實際與期望",
        "window_caption": "每條線代表所選家族在該窗口中最突出的候選；提示同時顯示實際聚集分數、條件式隨機期望、偏離與校正結果。",
        "holdout_title": "時間留出驗證",
        "holdout_caption": "先以前 {training:,} 期選出每個家族在 5 期與 10 期窗口最突出的候選，再以前述以外的 {holdout:,} 期獨立檢驗。跨五個家族的候選再作 Holm 校正。",
        "flow_title": "研究流程：探索期至留出期",
        "flow_caption": "所有探索期候選均需在未參與選擇的後續期數重現；目前兩個窗口均沒有候選通過。",
        "methods_title": "研究方法與判讀限制",
        "methods_text": """
- **總頻率**：比較組合實際出現次數與均勻 49 選 6 的理論期望；原始 p 值會因大量同時檢驗而自然出現少數偏離，故必須配合 Holm 校正。
- **5／10 期窗口**：固定組合的實際出現總數，只檢查其在相鄰窗口中是否異常集中或分散，避免把「總出現較多」錯當成跨期週期。
- **留出驗證**：探索期選出的候選，必須在之後未參與篩選的新期數重現，才可成為未來盲測的研究候選。

六合彩攪珠應視為獨立隨機事件。本區只供統計教育與模型治理研究，不構成投注建議或中獎保證。
""",
    },
    "en": {
        "language_label": "Display language",
        "language_help": "Only the window-research copy, tables, chart labels, and tooltips change. Statistical values and testing rules stay unchanged.",
        "title": "5/10-draw window frequency research",
        "intro": "This view presents a versioned long-run research snapshot. It uses a uniform 6-from-49 benchmark and Holm multiple-testing correction within each combination family. It does not alter the model, blind-test ledger, or weights.",
        "family_filter": "Combination-family filter",
        "family_filter_help": "The filter updates the family summary, full-sample candidates, total-frequency chart, and temporal holdout views together. Clear all options to inspect the empty state.",
        "sample": "Research sample",
        "tests": "Predefined tests",
        "five_signals": "5-draw full-sample candidates",
        "holdout_passed": "Passed holdout",
        "no_families": "No combination family is selected. Choose at least one family above to display the research tables and charts.",
        "range": "Data range: {start} to {end}. Within the selected families, the few apparent full-sample deviations did not pass validation in the later {holdout:,} held-out draws; they are therefore not model signals.",
        "summary_title": "Family summary: total-frequency and window deviations",
        "signal_holdout_title": "5/10-draw full-sample candidates and holdout validation",
        "signal_holdout_caption": "Bars count exploratory candidates passing the within-family Holm correction. Only candidates that also pass holdout validation are research signals worth tracking.",
        "frequency_title": "Observed frequency vs random expectation: hover for details",
        "frequency_caption": "Hover over a bar to view the candidate pattern, observed draws, random expectation, deviation, and Holm-correction information. All candidates remain research screens, not predictive signals.",
        "window_title": "5/10-draw window-score trend: hover for observed and expected values",
        "window_caption": "Each line represents the most prominent candidate in a selected family for that window. Tooltips show the observed clustering score, conditional random expectation, deviation, and correction result.",
        "holdout_title": "Temporal holdout validation",
        "holdout_caption": "The most prominent candidate for each family and 5/10-draw window is selected from the first {training:,} draws, then independently tested on the following {holdout:,} draws. The selected candidates receive a Holm correction across families.",
        "flow_title": "Research flow: exploration to holdout",
        "flow_caption": "Every exploratory candidate must replicate in later draws that did not participate in selection. At present, no candidate passes either window's holdout validation.",
        "methods_title": "Methods and interpretation limits",
        "methods_text": """
- **Total frequency**: compares observed combination counts with the theoretical expectation under uniform 6-from-49 draws. Raw p-values naturally contain some deviations after many simultaneous tests, so Holm correction is required.
- **5/10-draw windows**: conditions on a combination's observed total count and tests only whether its appearances are unusually clustered or dispersed in adjacent windows. This prevents a high total count from being mistaken for a cycle.
- **Holdout validation**: a candidate selected in the exploration period must reproduce in later draws not used for selection before it can become a prospective blind-test research candidate.

Mark Six draws should be treated as independent random events. This view is for statistical education and model-governance research only; it is not betting advice or a guarantee of any result.
""",
    },
}

FAMILY_TRANSLATIONS = {
    "三區精確分布": "Exact low/mid/high distribution",
    "同尾數至少兩個": "At least two with the same terminal digit",
    "奇偶精確分布": "Exact odd/even distribution",
    "所有指定號碼對": "All specified number pairs",
    "連號對": "Consecutive pairs",
}

COLUMN_TRANSLATIONS = {
    "組合家族": "Combination family",
    "同時檢驗數": "Tests",
    "總頻率原始偏離數": "Unadjusted frequency deviations",
    "總頻率 Holm 顯著數": "Frequency Holm discoveries",
    "5期 Holm 顯著數": "5-draw Holm discoveries",
    "10期 Holm 顯著數": "10-draw Holm discoveries",
    "5期最突出候選": "Top 5-draw candidate",
    "10期最突出候選": "Top 10-draw candidate",
    "5期原始 p": "5-draw raw p",
    "10期原始 p": "10-draw raw p",
    "5期方向": "5-draw direction",
    "10期方向": "10-draw direction",
    "窗口": "Window",
    "探索期選出候選": "Exploration candidate",
    "留出期方向": "Holdout direction",
    "留出期原始 p": "Holdout raw p",
    "跨家族 Holm p": "Across-family Holm p",
    "通過留出驗證": "Passed holdout",
    "全樣本 Holm 候選": "Full-sample Holm candidates",
    "留出驗證通過": "Passed holdout",
    "探索期候選": "Exploration candidates",
    "候選模式": "Candidate pattern",
    "實際出現期數": "Observed draws",
    "隨機期望期數": "Random expected draws",
    "頻率偏離": "Frequency deviation",
    "基準機率": "Baseline probability",
    "總頻率原始 p": "Frequency raw p",
    "總頻率 Holm p": "Frequency Holm p",
    "總頻率 Holm 狀態": "Frequency Holm status",
    "數據系列": "Data series",
    "期數": "Draws",
    "實際窗口分數": "Observed window score",
    "隨機期望分數": "Random expected score",
    "窗口偏離": "Window deviation",
    "方向": "Direction",
    "窗口原始 p": "Window raw p",
    "窗口 Holm p": "Window Holm p",
    "窗口 Holm 狀態": "Window Holm status",
    "分數": "Score",
}

VALUE_TRANSLATIONS = {
    "通過": "Pass",
    "未通過": "Not passed",
    "是": "Yes",
    "否": "No",
    "較集中": "More clustered",
    "較分散": "More dispersed",
    "實際出現期數": "Observed draws",
    "隨機期望期數": "Random expected draws",
    "實際窗口分數": "Observed window score",
    "隨機期望分數": "Random expected score",
    "5 期": "5 draws",
    "10 期": "10 draws",
}


def research_copy(language: str) -> dict[str, str]:
    """Return the copy dictionary for the requested window-research language."""
    return RESEARCH_COPY["en" if language == "en" else "zh"]


def family_display_name(family: str, language: str) -> str:
    """Map a canonical Chinese family key to its display name."""
    return FAMILY_TRANSLATIONS.get(family, family) if language == "en" else family


def canonical_family_name(display_name: str, language: str) -> str:
    """Map a family option selected in the UI back to the canonical research key."""
    if language != "en":
        return display_name
    return next(
        (canonical for canonical, translated in FAMILY_TRANSLATIONS.items() if translated == display_name),
        display_name,
    )


def _localize_pattern(value: object) -> object:
    if not isinstance(value, str):
        return value
    localized = value.replace("號碼對 ", "Pair ").replace("連號 ", "Consecutive ")
    localized = re.sub(r"尾數 (\d)（至少兩個）", r"Terminal digit \1 (at least two)", localized)
    localized = re.sub(r"(\d) 奇 (\d) 偶", r"\1 odd / \2 even", localized)
    localized = localized.replace("低中高 =", "Low / Mid / High =")
    return localized


def _localize_frame(frame: pd.DataFrame, language: str) -> pd.DataFrame:
    if language != "en" or frame.empty:
        return frame.copy()
    translated = frame.copy()
    for column, mapper in {
        "組合家族": lambda value: family_display_name(str(value), "en"),
        "候選模式": _localize_pattern,
        "探索期選出候選": _localize_pattern,
        "5期最突出候選": _localize_pattern,
        "10期最突出候選": _localize_pattern,
    }.items():
        if column in translated.columns:
            translated[column] = translated[column].map(mapper)
    for column in ("方向", "留出期方向", "5期方向", "10期方向", "總頻率 Holm 狀態", "窗口 Holm 狀態", "通過留出驗證", "數據系列", "窗口"):
        if column in translated.columns:
            translated[column] = translated[column].map(lambda value: VALUE_TRANSLATIONS.get(value, value))
    return translated.rename(columns=COLUMN_TRANSLATIONS)


def localize_long_window_research(state: dict[str, Any], language: str) -> dict[str, Any]:
    """Translate all window-research display tables and chart data without changing statistics."""
    if language != "en" or not state.get("available"):
        return state
    localized = dict(state)
    for key in (
        "family_table",
        "holdout_table",
        "frequency_detail_table",
        "window_score_table",
        "frequency_tooltip_chart",
        "window_tooltip_chart",
    ):
        localized[key] = _localize_frame(state[key], language)
    for key in ("window_signal_chart", "frequency_chart", "holdout_flow_chart"):
        chart = state[key].copy()
        chart.index = [VALUE_TRANSLATIONS.get(value, family_display_name(str(value), "en")) for value in chart.index]
        localized[key] = chart.rename(columns=COLUMN_TRANSLATIONS)
    return localized


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
