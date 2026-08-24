"""Describe short-run recurrence of common Mark Six pattern events.

This script is deliberately read-only: it never writes prediction, blind-test,
or production lottery-history files.  It evaluates a pre-defined family of
common pattern events against the uniform 49-choose-6 baseline and uses Holm
family-wise correction within each pattern family.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Callable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "lotto_history_extended_2002_2026.csv"
LATEST = ROOT / "data" / "lotto_history_real.csv"
OUTPUT = ROOT / "analysis-output" / "common_pattern_streak_analysis.json"
SUMMARY_OUTPUT = ROOT / "analysis-output" / "common_pattern_streak_analysis.md"
NUMBER_COLUMNS = [f"N{index}" for index in range(1, 7)]
TOTAL_COMBINATIONS = math.comb(49, 6)


@dataclass(frozen=True)
class Pattern:
    family: str
    label: str
    probability: float
    match: Callable[[frozenset[int]], bool]


def hypergeometric_exact(group_sizes: tuple[int, ...], selected: tuple[int, ...]) -> float:
    numerator = math.prod(math.comb(size, count) for size, count in zip(group_sizes, selected))
    return numerator / TOTAL_COMBINATIONS


def hypergeometric_at_least_two(group_size: int) -> float:
    return sum(
        math.comb(group_size, selected) * math.comb(49 - group_size, 6 - selected)
        for selected in range(2, min(group_size, 6) + 1)
    ) / TOTAL_COMBINATIONS


def binomial_upper_tail(successes: int, trials: int, probability: float) -> float | None:
    """P(Binomial(trials, probability) >= successes), computed in log space."""
    if trials <= 0:
        return None
    if successes <= 0:
        return 1.0
    if probability <= 0:
        return 0.0
    if probability >= 1:
        return 1.0
    log_terms = [
        math.lgamma(trials + 1)
        - math.lgamma(count + 1)
        - math.lgamma(trials - count + 1)
        + count * math.log(probability)
        + (trials - count) * math.log1p(-probability)
        for count in range(successes, trials + 1)
    ]
    maximum = max(log_terms)
    return float(min(1.0, math.exp(maximum) * sum(math.exp(term - maximum) for term in log_terms)))


def holm_adjust(p_values: list[float | None]) -> list[float | None]:
    """Holm family-wise adjusted p-values, retaining None for unavailable tests."""
    indexed = [(index, value) for index, value in enumerate(p_values) if value is not None]
    if not indexed:
        return [None] * len(p_values)
    ordered = sorted(indexed, key=lambda item: item[1])
    adjusted: dict[int, float] = {}
    running_max = 0.0
    m = len(ordered)
    for rank, (index, value) in enumerate(ordered):
        running_max = max(running_max, min(1.0, value * (m - rank)))
        adjusted[index] = running_max
    return [adjusted.get(index) for index in range(len(p_values))]


def longest_run(flags: list[bool]) -> int:
    longest = 0
    current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return longest


def make_patterns() -> list[Pattern]:
    patterns: list[Pattern] = []

    pair_probability = math.comb(47, 4) / TOTAL_COMBINATIONS
    for first, second in combinations(range(1, 50), 2):
        patterns.append(
            Pattern(
                family="所有指定號碼對",
                label=f"號碼對 {first:02d}-{second:02d}",
                probability=pair_probability,
                match=lambda draw, first=first, second=second: first in draw and second in draw,
            )
        )

    for first in range(1, 49):
        second = first + 1
        patterns.append(
            Pattern(
                family="連號對",
                label=f"連號 {first:02d}-{second:02d}",
                probability=pair_probability,
                match=lambda draw, first=first, second=second: first in draw and second in draw,
            )
        )

    for tail in range(10):
        members = frozenset(number for number in range(1, 50) if number % 10 == tail)
        patterns.append(
            Pattern(
                family="同尾數至少兩個",
                label=f"尾數 {tail}（至少兩個）",
                probability=hypergeometric_at_least_two(len(members)),
                match=lambda draw, members=members: len(draw & members) >= 2,
            )
        )

    for odd_count in range(7):
        patterns.append(
            Pattern(
                family="奇偶精確分布",
                label=f"{odd_count} 奇 {6 - odd_count} 偶",
                probability=hypergeometric_exact((25, 24), (odd_count, 6 - odd_count)),
                match=lambda draw, odd_count=odd_count: sum(number % 2 for number in draw) == odd_count,
            )
        )

    zones = (frozenset(range(1, 17)), frozenset(range(17, 34)), frozenset(range(34, 50)))
    for low_count in range(7):
        for mid_count in range(7 - low_count):
            high_count = 6 - low_count - mid_count
            counts = (low_count, mid_count, high_count)
            patterns.append(
                Pattern(
                    family="三區精確分布",
                    label=f"低中高 = {low_count}-{mid_count}-{high_count}",
                    probability=hypergeometric_exact((16, 17, 16), counts),
                    match=lambda draw, counts=counts, zones=zones: tuple(len(draw & zone) for zone in zones) == counts,
                )
            )
    return patterns


def analyze_pattern(pattern: Pattern, draws: list[frozenset[int]]) -> dict[str, object]:
    flags = [pattern.match(draw) for draw in draws]
    observed = sum(flags)
    after_one_trials = max(observed - int(flags[-1]), 0)
    after_one_successes = sum(int(flags[index - 1] and flags[index]) for index in range(1, len(flags)))
    after_two_trials = sum(
        int(flags[index - 1] and flags[index - 2]) for index in range(2, len(flags))
    )
    after_two_successes = sum(
        int(flags[index - 2] and flags[index - 1] and flags[index]) for index in range(2, len(flags))
    )
    return {
        "family": pattern.family,
        "pattern": pattern.label,
        "baseline_probability": pattern.probability,
        "observed_draws": observed,
        "expected_draws": len(draws) * pattern.probability,
        "observed_rate": observed / len(draws),
        "longest_run": longest_run(flags),
        "after_one": {
            "trials": after_one_trials,
            "successes": after_one_successes,
            "rate": after_one_successes / after_one_trials if after_one_trials else None,
            "unadjusted_upper_tail_p": binomial_upper_tail(after_one_successes, after_one_trials, pattern.probability),
        },
        "after_two": {
            "trials": after_two_trials,
            "successes": after_two_successes,
            "rate": after_two_successes / after_two_trials if after_two_trials else None,
            "unadjusted_upper_tail_p": binomial_upper_tail(after_two_successes, after_two_trials, pattern.probability),
        },
    }


def main() -> None:
    archive = pd.read_csv(ARCHIVE)
    latest = pd.read_csv(LATEST)
    merged = pd.concat([archive, latest], ignore_index=True).drop_duplicates(subset=["Draw"], keep="last")
    merged["Date"] = pd.to_datetime(merged["Date"])
    merged = merged.sort_values(["Date", "Draw"]).reset_index(drop=True)
    draws = [frozenset(int(row[column]) for column in NUMBER_COLUMNS) for _, row in merged.iterrows()]

    patterns = make_patterns()
    results = [analyze_pattern(pattern, draws) for pattern in patterns]
    for horizon in ("after_one", "after_two"):
        by_family: dict[str, list[int]] = {}
        for index, result in enumerate(results):
            by_family.setdefault(str(result["family"]), []).append(index)
        for family_indexes in by_family.values():
            p_values = [results[index][horizon]["unadjusted_upper_tail_p"] for index in family_indexes]
            for index, adjusted in zip(family_indexes, holm_adjust(p_values)):
                results[index][horizon]["holm_adjusted_p"] = adjusted
                results[index][horizon]["significant_at_0_05"] = bool(adjusted is not None and adjusted < 0.05)

    report = {
        "method": {
            "draw_count": len(draws),
            "date_range": [str(merged["Date"].min().date()), str(merged["Date"].max().date())],
            "sources": [str(ARCHIVE.relative_to(ROOT)), str(LATEST.relative_to(ROOT))],
            "interpretation": "One-sided tests assess whether a pattern repeats more often than its uniform 49-choose-6 baseline. Holm correction is applied separately within each pre-defined pattern family.",
        },
        "families": {},
    }
    for family in sorted({str(result["family"]) for result in results}):
        family_results = [result for result in results if result["family"] == family]
        report["families"][family] = {
            "tests": len(family_results),
            "after_one_significant": [
                result for result in family_results if result["after_one"]["significant_at_0_05"]
            ],
            "after_two_significant": [
                result for result in family_results if result["after_two"]["significant_at_0_05"]
            ],
            "top_after_one_unadjusted": sorted(
                family_results,
                key=lambda result: (
                    result["after_one"]["unadjusted_upper_tail_p"] is None,
                    result["after_one"]["unadjusted_upper_tail_p"] or 1.0,
                ),
            )[:5],
            "top_after_two_unadjusted": sorted(
                family_results,
                key=lambda result: (
                    result["after_two"]["unadjusted_upper_tail_p"] is None,
                    result["after_two"]["unadjusted_upper_tail_p"] or 1.0,
                ),
            )[:5],
        }

    # A simple temporal holdout prevents the most eye-catching historical
    # candidate in each family from being reported without a fresh check.
    # Candidate selection uses the earlier 75% only; the final 25% remains
    # untouched until this evaluation.
    split_index = int(len(draws) * 0.75)
    training_draws = draws[:split_index]
    holdout_draws = draws[split_index:]
    training_results = [analyze_pattern(pattern, training_draws) for pattern in patterns]
    selected_indexes: list[int] = []
    for family in sorted({pattern.family for pattern in patterns}):
        family_indexes = [index for index, pattern in enumerate(patterns) if pattern.family == family]
        selected_indexes.append(
            min(
                family_indexes,
                key=lambda index: training_results[index]["after_one"]["unadjusted_upper_tail_p"]
                if training_results[index]["after_one"]["unadjusted_upper_tail_p"] is not None
                else 1.0,
            )
        )
    holdout_candidates = [analyze_pattern(patterns[index], holdout_draws) for index in selected_indexes]
    holdout_adjusted = holm_adjust(
        [candidate["after_one"]["unadjusted_upper_tail_p"] for candidate in holdout_candidates]
    )
    for candidate, adjusted in zip(holdout_candidates, holdout_adjusted):
        candidate["after_one"]["holm_adjusted_p_across_selected_families"] = adjusted
        candidate["after_one"]["significant_at_0_05"] = bool(adjusted is not None and adjusted < 0.05)
    report["temporal_holdout"] = {
        "training_draws": len(training_draws),
        "holdout_draws": len(holdout_draws),
        "selection_rule": "Within each pattern family, select the lowest unadjusted one-draw recurrence p-value in the earlier 75% of draws; evaluate it once in the later 25%, then Holm-correct across the five selected family candidates.",
        "candidates": holdout_candidates,
    }

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_lines = [
        "# 常見六合彩組合：短期連莊偏差篩查",
        "",
        "本報告只使用長期實際主號資料，並以均勻 `49 選 6` 基準測試某一類組合在已出現後是否於下一期或連續兩期後更常重現。所有檢驗均為單側『重現率較高』檢定；每個預先定義的組合家族各自採用 Holm 家族錯誤率校正。這些檢驗用於排除事後挑選雜訊，不產生投注建議。",
        "",
        f"資料：{report['method']['draw_count']:,} 期（{report['method']['date_range'][0]} 至 {report['method']['date_range'][1]}）。",
        "",
        "| 組合家族 | 同時檢驗數 | 一期後校正顯著數 | 兩連後校正顯著數 | 一期後最小未校正 p 值 | 兩連後最小未校正 p 值 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for family, values in report["families"].items():
        first_after_one = values["top_after_one_unadjusted"][0]
        first_after_two = values["top_after_two_unadjusted"][0]
        one_p = first_after_one["after_one"]["unadjusted_upper_tail_p"]
        two_p = first_after_two["after_two"]["unadjusted_upper_tail_p"]
        summary_lines.append(
            "| {family} | {tests} | {one_count} | {two_count} | {one_pattern}: {one_p:.4g} | {two_pattern}: {two_p:.4g} |".format(
                family=family,
                tests=values["tests"],
                one_count=len(values["after_one_significant"]),
                two_count=len(values["after_two_significant"]),
                one_pattern=first_after_one["pattern"],
                one_p=one_p if one_p is not None else 1.0,
                two_pattern=first_after_two["pattern"],
                two_p=two_p if two_p is not None else 1.0,
            )
        )
    summary_lines.extend(
        [
            "",
            "## 時間留出驗證",
            "",
            f"先以前 {report['temporal_holdout']['training_draws']:,} 期選出每個家族最突出的『一期後重現』候選，再在其後 {report['temporal_holdout']['holdout_draws']:,} 期只檢驗一次；五個候選再共同作 Holm 校正。",
            "",
            "| 家族 | 訓練期選出的候選 | 留出期下一期重現率 | 留出期未校正 p 值 | 跨五個候選 Holm p 值 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for candidate in report["temporal_holdout"]["candidates"]:
        values = candidate["after_one"]
        summary_lines.append(
            "| {family} | {pattern} | {rate:.2%} | {raw:.4g} | {adjusted:.4g} |".format(
                family=candidate["family"],
                pattern=candidate["pattern"],
                rate=values["rate"] if values["rate"] is not None else 0.0,
                raw=values["unadjusted_upper_tail_p"] if values["unadjusted_upper_tail_p"] is not None else 1.0,
                adjusted=values["holm_adjusted_p_across_selected_families"]
                if values["holm_adjusted_p_across_selected_families"] is not None
                else 1.0,
            )
        )
    summary_lines.extend(
        [
            "",
            "## 判讀規則",
            "",
            "只有 Holm 校正後 p 值小於 0.05 的結果，才可被標記為該家族中的正式研究候選；即使達標，也須以之後未參與篩選的新期數進行預先註冊的盲測確認。最小的未校正 p 值只反映在大量搜尋後最突出的表面現象，不能單獨用作模型加權或預測依據。",
            "",
            "> 六合彩結果應視為獨立隨機事件。本篩查只供統計教育與模型治理，不保證任何未來結果，亦不構成投注建議。",
        ]
    )
    SUMMARY_OUTPUT.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
