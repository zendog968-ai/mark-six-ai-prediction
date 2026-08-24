"""Test common Mark Six pattern frequencies over 5- and 10-draw windows.

For each predefined pattern event, the script separates two questions:
1. Is its total frequency compatible with the uniform 49-choose-6 baseline?
2. Conditional on that observed total, are its appearances unusually clustered
   or unusually dispersed across rolling 5- and 10-draw windows?

The second statistic counts each pair of event occurrences jointly present in
rolling windows. Its conditional random-position expectation and variance are
calculated exactly; a normal approximation is used only when the conditional
variance is positive and the observed event count is sufficiently large.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_common_pattern_streaks import NUMBER_COLUMNS, ROOT, Pattern, holm_adjust, make_patterns


ARCHIVE = ROOT / "data" / "lotto_history_extended_2002_2026.csv"
LATEST = ROOT / "data" / "lotto_history_real.csv"
OUTPUT = ROOT / "analysis-output" / "long_window_pattern_analysis.json"
SUMMARY_OUTPUT = ROOT / "analysis-output" / "long_window_pattern_analysis.md"
WINDOWS = (5, 10)


def two_sided_normal_p(z_score: float) -> float:
    return math.erfc(abs(z_score) / math.sqrt(2))


def binomial_normal_test(observed: int, trials: int, probability: float) -> tuple[float | None, float | None]:
    """Return normal z and two-sided p for total frequency when E[X] >= 5."""
    variance = trials * probability * (1 - probability)
    expected = trials * probability
    if expected < 5 or variance <= 0:
        return None, None
    z_score = (observed - expected) / math.sqrt(variance)
    return z_score, two_sided_normal_p(z_score)


def window_geometry(length: int, window: int) -> dict[str, float]:
    """Weighted edge sums for all pairs that share a rolling window."""
    edge_weight_sum = 0.0
    edge_square_sum = 0.0
    incident_weight_sum = np.zeros(length, dtype=float)
    incident_square_sum = np.zeros(length, dtype=float)
    for lag in range(1, window):
        weight = float(window - lag)
        count = length - lag
        edge_weight_sum += count * weight
        edge_square_sum += count * weight * weight
        incident_weight_sum[:-lag] += weight
        incident_weight_sum[lag:] += weight
        incident_square_sum[:-lag] += weight * weight
        incident_square_sum[lag:] += weight * weight
    shared_edge_pair_weight = float(
        np.sum((incident_weight_sum**2 - incident_square_sum) / 2)
    )
    all_distinct_edge_pair_weight = (edge_weight_sum**2 - edge_square_sum) / 2 - shared_edge_pair_weight
    return {
        "edge_weight_sum": edge_weight_sum,
        "edge_square_sum": edge_square_sum,
        "shared_edge_pair_weight": shared_edge_pair_weight,
        "disjoint_edge_pair_weight": all_distinct_edge_pair_weight,
    }


def conditional_clumping(
    flags: np.ndarray, window: int, geometry: dict[str, float]
) -> dict[str, float | int | None]:
    """Compare rolling-window clumping against random placement of equal event total."""
    length = len(flags)
    event_total = int(flags.sum())
    indicator = flags.astype(int)
    profile = np.convolve(indicator, np.ones(window, dtype=int), mode="valid")
    observed_score = float(
        sum((window - lag) * np.dot(indicator[:-lag], indicator[lag:]) for lag in range(1, window))
    )
    if event_total < 4:
        return {
            "observed_score": observed_score,
            "expected_score": None,
            "z_score": None,
            "two_sided_p": None,
            "profile_mean": float(profile.mean()),
            "profile_variance": float(profile.var(ddof=1)) if len(profile) > 1 else 0.0,
            "profile_maximum": int(profile.max()),
            "interpretation": "事件太少，未作正式條件式窗口聚集檢定。",
        }

    probability_2 = event_total * (event_total - 1) / (length * (length - 1))
    probability_3 = (
        event_total * (event_total - 1) * (event_total - 2) / (length * (length - 1) * (length - 2))
    )
    probability_4 = (
        event_total
        * (event_total - 1)
        * (event_total - 2)
        * (event_total - 3)
        / (length * (length - 1) * (length - 2) * (length - 3))
    )
    expected_score = geometry["edge_weight_sum"] * probability_2
    variance = (
        geometry["edge_square_sum"] * (probability_2 - probability_2**2)
        + 2 * geometry["shared_edge_pair_weight"] * (probability_3 - probability_2**2)
        + 2 * geometry["disjoint_edge_pair_weight"] * (probability_4 - probability_2**2)
    )
    variance = max(float(variance), 0.0)
    if variance <= 0:
        z_score = None
        p_value = None
        interpretation = "條件式方差為零，未作正式檢定。"
    else:
        z_score = (observed_score - expected_score) / math.sqrt(variance)
        p_value = two_sided_normal_p(z_score)
        interpretation = "較集中" if z_score > 0 else "較分散"
    return {
        "observed_score": observed_score,
        "expected_score": expected_score,
        "z_score": z_score,
        "two_sided_p": p_value,
        "profile_mean": float(profile.mean()),
        "profile_variance": float(profile.var(ddof=1)) if len(profile) > 1 else 0.0,
        "profile_maximum": int(profile.max()),
        "interpretation": interpretation,
    }


def analyze_pattern(
    pattern: Pattern, draws: list[frozenset[int]], geometries: dict[int, dict[str, float]]
) -> dict[str, object]:
    flags = np.array([pattern.match(draw) for draw in draws], dtype=bool)
    observed = int(flags.sum())
    frequency_z, frequency_p = binomial_normal_test(observed, len(draws), pattern.probability)
    return {
        "family": pattern.family,
        "pattern": pattern.label,
        "baseline_probability": pattern.probability,
        "observed_draws": observed,
        "expected_draws": len(draws) * pattern.probability,
        "frequency_z_score": frequency_z,
        "frequency_two_sided_p": frequency_p,
        "windows": {
            str(window): conditional_clumping(flags, window, geometries[window]) for window in WINDOWS
        },
    }


def annotate_holm(results: list[dict[str, object]]) -> None:
    for family in sorted({str(result["family"]) for result in results}):
        family_results = [result for result in results if result["family"] == family]
        frequency_adjusted = holm_adjust([result["frequency_two_sided_p"] for result in family_results])
        for result, adjusted in zip(family_results, frequency_adjusted):
            result["frequency_holm_adjusted_p"] = adjusted
            result["frequency_significant_at_0_05"] = bool(adjusted is not None and adjusted < 0.05)
        for window in WINDOWS:
            p_values = [result["windows"][str(window)]["two_sided_p"] for result in family_results]
            for result, adjusted in zip(family_results, holm_adjust(p_values)):
                values = result["windows"][str(window)]
                values["holm_adjusted_p_within_window"] = adjusted
                values["significant_at_0_05"] = bool(adjusted is not None and adjusted < 0.05)


def sort_by_p(results: list[dict[str, object]], window: int) -> list[dict[str, object]]:
    return sorted(
        results,
        key=lambda result: (
            result["windows"][str(window)]["two_sided_p"] is None,
            result["windows"][str(window)]["two_sided_p"] or 1.0,
        ),
    )


def main() -> None:
    archive = pd.read_csv(ARCHIVE)
    latest = pd.read_csv(LATEST)
    frame = pd.concat([archive, latest], ignore_index=True).drop_duplicates(subset=["Draw"], keep="last")
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.sort_values(["Date", "Draw"]).reset_index(drop=True)
    draws = [frozenset(int(row[column]) for column in NUMBER_COLUMNS) for _, row in frame.iterrows()]
    patterns = make_patterns()
    geometries = {window: window_geometry(len(draws), window) for window in WINDOWS}
    results = [analyze_pattern(pattern, draws, geometries) for pattern in patterns]
    annotate_holm(results)

    split_index = int(len(draws) * 0.75)
    train_draws = draws[:split_index]
    holdout_draws = draws[split_index:]
    train_geometries = {window: window_geometry(len(train_draws), window) for window in WINDOWS}
    holdout_geometries = {window: window_geometry(len(holdout_draws), window) for window in WINDOWS}
    train_results = [analyze_pattern(pattern, train_draws, train_geometries) for pattern in patterns]
    holdout_candidates: list[dict[str, object]] = []
    for family in sorted({pattern.family for pattern in patterns}):
        family_indexes = [index for index, pattern in enumerate(patterns) if pattern.family == family]
        for window in WINDOWS:
            selected = min(
                family_indexes,
                key=lambda index: train_results[index]["windows"][str(window)]["two_sided_p"]
                if train_results[index]["windows"][str(window)]["two_sided_p"] is not None
                else 1.0,
            )
            candidate = analyze_pattern(patterns[selected], holdout_draws, holdout_geometries)
            candidate["selected_from"] = {"family": family, "window": window}
            holdout_candidates.append(candidate)
    for window in WINDOWS:
        candidates = [candidate for candidate in holdout_candidates if candidate["selected_from"]["window"] == window]
        adjusted = holm_adjust([candidate["windows"][str(window)]["two_sided_p"] for candidate in candidates])
        for candidate, p_value in zip(candidates, adjusted):
            values = candidate["windows"][str(window)]
            values["holm_adjusted_p_across_selected_families"] = p_value
            values["significant_at_0_05"] = bool(p_value is not None and p_value < 0.05)

    report: dict[str, object] = {
        "method": {
            "draw_count": len(draws),
            "date_range": [str(frame["Date"].min().date()), str(frame["Date"].max().date())],
            "sources": [str(ARCHIVE.relative_to(ROOT)), str(LATEST.relative_to(ROOT))],
            "frequency_test": "Two-sided normal approximation to the binomial total-frequency baseline, omitted where the expected total is below five.",
            "window_test": "Conditional random-position test: event totals are held fixed and rolling-window pair co-occurrence is compared with its exact null expectation and variance. The reported two-sided p-value uses a normal approximation to that conditional statistic.",
            "correction": "Holm correction is applied separately for each predefined family and each window length.",
        },
        "families": {},
        "temporal_holdout": {
            "training_draws": len(train_draws),
            "holdout_draws": len(holdout_draws),
            "selection_rule": "For each family and each window length, select the smallest raw conditional window p-value from the earlier 75% of draws. Test that one selected candidate on the final 25%; Holm-correct across the five family candidates for that same window length.",
            "candidates": holdout_candidates,
        },
    }
    for family in sorted({str(result["family"]) for result in results}):
        family_results = [result for result in results if result["family"] == family]
        report["families"][family] = {
            "tests": len(family_results),
            "frequency_significant_unadjusted": [
                result for result in family_results if result["frequency_two_sided_p"] is not None and result["frequency_two_sided_p"] < 0.05
            ],
            "frequency_significant_holm": [
                result for result in family_results if result["frequency_significant_at_0_05"]
            ],
            "windows": {
                str(window): {
                    "significant": [
                        result for result in family_results if result["windows"][str(window)]["significant_at_0_05"]
                    ],
                    "top_raw": sort_by_p(family_results, window)[:5],
                }
                for window in WINDOWS
            },
        }

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 常見六合彩組合：五期與十期窗口頻率檢驗",
        "",
        "本分析使用每期六個主號的長期真實資料。每個組合先與均勻 `49 選 6` 的單期出現機率比較總頻率；再固定該組合實際出現總數，檢查其在所有滾動 5 期及 10 期窗口中是否異常集中或異常分散。後者不會把總出現偏多誤判為時間聚集。",
        "",
        f"資料：{len(draws):,} 期（{report['method']['date_range'][0]} 至 {report['method']['date_range'][1]}）。",
        "",
        "| 組合家族 | 檢驗數 | 總頻率偏離數（原始／Holm） | 5 期校正顯著數 | 10 期校正顯著數 | 5 期最小原始 p | 10 期最小原始 p |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for family, values in report["families"].items():
        top_5 = values["windows"]["5"]["top_raw"][0]
        top_10 = values["windows"]["10"]["top_raw"][0]
        p_5 = top_5["windows"]["5"]["two_sided_p"]
        p_10 = top_10["windows"]["10"]["two_sided_p"]
        lines.append(
            "| {family} | {tests} | {frequency} | {five_sig} | {ten_sig} | {five_pattern}: {five_p:.4g} | {ten_pattern}: {ten_p:.4g} |".format(
                family=family,
                tests=values["tests"],
                frequency=f"{len(values['frequency_significant_unadjusted'])}／{len(values['frequency_significant_holm'])}",
                five_sig=len(values["windows"]["5"]["significant"]),
                ten_sig=len(values["windows"]["10"]["significant"]),
                five_pattern=top_5["pattern"],
                five_p=p_5 if p_5 is not None else 1.0,
                ten_pattern=top_10["pattern"],
                ten_p=p_10 if p_10 is not None else 1.0,
            )
        )
    lines.extend(
        [
            "",
            "## 時間留出驗證",
            "",
            f"以前 {len(train_draws):,} 期探索各家族在每個窗口最突出的候選，再以後 {len(holdout_draws):,} 期檢驗。每個窗口長度均跨五個家族作 Holm 校正。",
            "",
            "| 窗口 | 家族 | 留出期候選 | 方向 | 留出期原始 p | Holm p |",
            "|---:|---|---|---|---:|---:|",
        ]
    )
    for candidate in sorted(holdout_candidates, key=lambda item: (item["selected_from"]["window"], item["family"])):
        window = candidate["selected_from"]["window"]
        values = candidate["windows"][str(window)]
        lines.append(
            "| {window} | {family} | {pattern} | {direction} | {raw:.4g} | {adjusted:.4g} |".format(
                window=window,
                family=candidate["family"],
                pattern=candidate["pattern"],
                direction=values["interpretation"],
                raw=values["two_sided_p"] if values["two_sided_p"] is not None else 1.0,
                adjusted=values.get("holm_adjusted_p_across_selected_families")
                if values.get("holm_adjusted_p_across_selected_families") is not None
                else 1.0,
            )
        )
    lines.extend(
        [
            "",
            "## 判讀",
            "",
            "若某類組合在總頻率看似偏高，但在固定出現總數後的窗口聚集檢驗不顯著，表示它沒有可辨識的跨期週期性；反之亦然。只有在校正後顯著且能通過時間留出驗證的訊號，才可進入未來盲測候選，並不可直接改動既有的正式模型權重。",
            "",
            "> 本報告只作統計教育與模型治理研究。六合彩攪珠應視為獨立隨機事件；分析不構成投注建議或中獎保證。",
        ]
    )
    SUMMARY_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
