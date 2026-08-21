"""Paired Brier-score inference for pre-locked Mark Six configurations.

Expected input: one row per settled target draw and one numeric Brier-score
column per configuration. All compared configurations must have been locked
before that same target draw was known. Lower Brier score is better.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


@dataclass(frozen=True)
class BootstrapResult:
    """One-sided paired comparison result: candidate Brier < baseline."""

    n_draws: int
    mean_difference: float
    ci95_lower: float
    ci95_upper: float
    p_value_one_sided: float


@dataclass(frozen=True)
class DieboldMarianoResult:
    """One-sided DM/HLN result: candidate Brier < baseline Brier."""

    n_draws: int
    mean_difference: float
    truncation_lag: int
    long_run_variance: float
    hln_correction: float
    dm_statistic: float
    p_value_one_sided: float


def brier_score_per_draw(probabilities: np.ndarray, actual_main_numbers: Iterable[Iterable[int]]) -> np.ndarray:
    """Return one Brier score per draw from an ``(n_draws, 49)`` matrix.

    ``actual_main_numbers`` must supply exactly six unique integers in 1..49
    per draw. The special number is deliberately excluded.
    """
    probability_matrix = np.asarray(probabilities, dtype=float)
    if probability_matrix.ndim != 2 or probability_matrix.shape[1] != 49:
        raise ValueError("probabilities 必須為 shape=(期數, 49) 的矩陣。")
    if not np.isfinite(probability_matrix).all() or ((probability_matrix < 0) | (probability_matrix > 1)).any():
        raise ValueError("所有機率必須是 0 到 1 的有限數值。")

    actual_rows = list(actual_main_numbers)
    if len(actual_rows) != len(probability_matrix):
        raise ValueError("實際主號期數必須與機率矩陣列數相同。")
    outcomes = np.zeros_like(probability_matrix, dtype=float)
    for row_index, numbers in enumerate(actual_rows):
        values = [int(number) for number in numbers]
        if len(values) != 6 or len(set(values)) != 6 or any(number < 1 or number > 49 for number in values):
            raise ValueError("每期必須提供 6 個不重複且介於 1 到 49 的正選號碼。")
        outcomes[row_index, np.asarray(values, dtype=int) - 1] = 1.0
    return np.mean((probability_matrix - outcomes) ** 2, axis=1)


def circular_moving_block_bootstrap_mean(
    differences: Iterable[float],
    *,
    block_length: int = 5,
    n_bootstrap: int = 5_000,
    seed: int = 20260820,
) -> BootstrapResult:
    """Estimate paired loss-difference uncertainty with circular block resampling.

    ``differences`` equals ``candidate_brier - baseline_brier`` for the same
    draws. A negative mean favours the candidate. The p value tests
    H0: E[d] = 0 against H1: E[d] < 0 by resampling the centred series.
    """
    values = np.asarray(list(differences), dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("至少需要 2 個同一期的成對 Brier 差異。")
    if not np.isfinite(values).all():
        raise ValueError("Brier 差異不可包含缺漏值或無限值。")
    if block_length < 1 or block_length > len(values):
        raise ValueError("block_length 必須介於 1 與樣本期數之間。")
    if n_bootstrap < 100:
        raise ValueError("n_bootstrap 至少需要 100 次。")

    rng = np.random.default_rng(seed)
    n_draws = len(values)
    starts = rng.integers(0, n_draws, size=(n_bootstrap, int(np.ceil(n_draws / block_length))))
    offsets = np.arange(block_length, dtype=int)
    indices = (starts[:, :, None] + offsets[None, None, :]) % n_draws
    indices = indices.reshape(n_bootstrap, -1)[:, :n_draws]

    bootstrap_means = values[indices].mean(axis=1)
    observed_mean = float(values.mean())
    centred_means = (values - observed_mean)[indices].mean(axis=1)
    # Add one to numerator/denominator so a finite simulation never reports p=0.
    p_value = float((1 + np.count_nonzero(centred_means <= observed_mean)) / (n_bootstrap + 1))
    return BootstrapResult(
        n_draws=n_draws,
        mean_difference=observed_mean,
        ci95_lower=float(np.quantile(bootstrap_means, 0.025)),
        ci95_upper=float(np.quantile(bootstrap_means, 0.975)),
        p_value_one_sided=p_value,
    )


def diebold_mariano_test(
    differences: Iterable[float],
    *,
    forecast_horizon: int = 1,
    truncation_lag: int | None = None,
) -> DieboldMarianoResult:
    """Run one-sided Diebold–Mariano with HLN small-sample correction.

    ``differences`` equals ``candidate_brier - baseline_brier``. The test is
    H0: E[d] = 0 against H1: E[d] < 0. A Bartlett/Newey-West long-run variance
    estimates serial dependence in the loss differential. With rolling model
    training, the default lag is ``floor(n ** (1 / 3))``. For one-draw-ahead
    Mark Six forecasts, keep ``forecast_horizon=1``.
    """
    values = np.asarray(list(differences), dtype=float)
    if values.ndim != 1 or len(values) < 3:
        raise ValueError("Diebold–Mariano 檢定至少需要 3 個同一期成對 Brier 差異。")
    if not np.isfinite(values).all():
        raise ValueError("Brier 差異不可包含缺漏值或無限值。")
    n_draws = len(values)
    if forecast_horizon < 1 or forecast_horizon > n_draws:
        raise ValueError("forecast_horizon 必須介於 1 與樣本期數之間。")
    if truncation_lag is None:
        truncation_lag = max(0, int(np.floor(n_draws ** (1 / 3))))
    if truncation_lag < 0 or truncation_lag >= n_draws:
        raise ValueError("truncation_lag 必須介於 0 與樣本期數減 1 之間。")

    observed_mean = float(values.mean())
    centered = values - observed_mean
    long_run_variance = float(np.mean(centered * centered))
    for lag in range(1, truncation_lag + 1):
        autocovariance = float(np.mean(centered[lag:] * centered[:-lag]))
        bartlett_weight = 1.0 - lag / (truncation_lag + 1.0)
        long_run_variance += 2.0 * bartlett_weight * autocovariance
    # Finite-sample numerical rounding can otherwise produce a tiny negative value.
    long_run_variance = max(long_run_variance, 0.0)

    correction_squared = (n_draws + 1 - 2 * forecast_horizon + forecast_horizon * (forecast_horizon - 1) / n_draws) / n_draws
    if correction_squared <= 0:
        raise ValueError("forecast_horizon 令 HLN 小樣本修正無效。")
    hln_correction = float(np.sqrt(correction_squared))

    if np.isclose(long_run_variance, 0.0):
        if np.isclose(observed_mean, 0.0):
            statistic, p_value = 0.0, 0.5
        elif observed_mean < 0:
            statistic, p_value = float("-inf"), 0.0
        else:
            statistic, p_value = float("inf"), 1.0
    else:
        statistic = float(hln_correction * observed_mean / np.sqrt(long_run_variance / n_draws))
        p_value = float(student_t.cdf(statistic, df=n_draws - 1))

    return DieboldMarianoResult(
        n_draws=n_draws,
        mean_difference=observed_mean,
        truncation_lag=truncation_lag,
        long_run_variance=long_run_variance,
        hln_correction=hln_correction,
        dm_statistic=statistic,
        p_value_one_sided=p_value,
    )


def holm_bonferroni(p_values: Mapping[str, float], *, alpha: float = 0.05) -> pd.DataFrame:
    """Return Holm-adjusted p values and rejections for one prespecified family."""
    if not p_values:
        raise ValueError("至少需要一個 p 值。")
    if not 0 < alpha < 1:
        raise ValueError("alpha 必須介於 0 與 1 之間。")
    names = list(p_values)
    raw = np.asarray([p_values[name] for name in names], dtype=float)
    if not np.isfinite(raw).all() or ((raw < 0) | (raw > 1)).any():
        raise ValueError("所有 p 值必須介於 0 與 1。")

    order = np.argsort(raw, kind="stable")
    sorted_raw = raw[order]
    m = len(raw)
    sorted_adjusted = np.maximum.accumulate((m - np.arange(m)) * sorted_raw).clip(0.0, 1.0)
    sorted_reject = np.zeros(m, dtype=bool)
    for rank, p_value in enumerate(sorted_raw):
        if p_value <= alpha / (m - rank):
            sorted_reject[rank] = True
        else:
            break

    adjusted = np.empty(m, dtype=float)
    rejected = np.zeros(m, dtype=bool)
    adjusted[order] = sorted_adjusted
    rejected[order] = sorted_reject
    return pd.DataFrame(
        {
            "configuration": names,
            "p_value_one_sided": raw,
            "p_value_holm": adjusted,
            "reject_equal_or_worse_brier": rejected,
        }
    )


def compare_configurations(
    brier_by_draw: pd.DataFrame,
    *,
    baseline: str,
    candidates: Iterable[str],
    draw_column: str = "Draw",
    block_length: int = 5,
    n_bootstrap: int = 5_000,
    alpha: float = 0.05,
    seed: int = 20260820,
    dm_forecast_horizon: int = 1,
    dm_truncation_lag: int | None = None,
) -> pd.DataFrame:
    """Compare candidates to one baseline on exact same settled draws.

    Bootstrap and DM p values are separately Holm-adjusted within the same
    prespecified candidate family. ``both_methods_support_candidate`` should be
    interpreted as a robustness flag, not as a second independent discovery.
    """
    candidate_names = list(candidates)
    if not candidate_names:
        raise ValueError("至少需要一個候選配置。")
    if baseline in candidate_names:
        raise ValueError("baseline 不可同時列為候選配置。")
    required = [draw_column, baseline, *candidate_names]
    missing = [column for column in required if column not in brier_by_draw.columns]
    if missing:
        raise ValueError(f"缺少必要欄位：{', '.join(missing)}。")
    selected = brier_by_draw.loc[:, required].copy()
    if selected[draw_column].duplicated().any():
        raise ValueError("每個期數只能有一列 Brier 紀錄。")
    selected = selected.dropna(axis=0, how="any")
    if len(selected) < 3:
        raise ValueError("共同已結算期數不足；Diebold–Mariano 檢定至少需要 3 期。")
    numeric = selected.loc[:, [baseline, *candidate_names]].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Brier 欄位必須為有限數值。")

    results: list[dict[str, object]] = []
    bootstrap_p_values: dict[str, float] = {}
    dm_p_values: dict[str, float] = {}
    baseline_mean = float(numeric[baseline].mean())
    for offset, candidate in enumerate(candidate_names):
        differences = numeric[candidate] - numeric[baseline]
        bootstrap = circular_moving_block_bootstrap_mean(
            differences,
            block_length=block_length,
            n_bootstrap=n_bootstrap,
            seed=seed + offset,
        )
        dm_result = diebold_mariano_test(
            differences,
            forecast_horizon=dm_forecast_horizon,
            truncation_lag=dm_truncation_lag,
        )
        bootstrap_p_values[candidate] = bootstrap.p_value_one_sided
        dm_p_values[candidate] = dm_result.p_value_one_sided
        row = asdict(bootstrap)
        row["bootstrap_p_value_one_sided"] = row.pop("p_value_one_sided")
        for key, value in asdict(dm_result).items():
            row[f"dm_{key}"] = value
        row.update(
            {
                "configuration": candidate,
                "baseline": baseline,
                "candidate_mean_brier": float(numeric[candidate].mean()),
                "baseline_mean_brier": baseline_mean,
                "brier_skill_score_vs_baseline": float(1.0 - numeric[candidate].mean() / baseline_mean),
            }
        )
        results.append(row)

    result_frame = pd.DataFrame(results)
    bootstrap_holm = holm_bonferroni(bootstrap_p_values, alpha=alpha).rename(
        columns={
            "p_value_one_sided": "bootstrap_p_value_one_sided_check",
            "p_value_holm": "bootstrap_p_value_holm",
            "reject_equal_or_worse_brier": "bootstrap_reject_equal_or_worse_brier",
        }
    )
    dm_holm = holm_bonferroni(dm_p_values, alpha=alpha).rename(
        columns={
            "p_value_one_sided": "dm_p_value_one_sided_check",
            "p_value_holm": "dm_p_value_holm",
            "reject_equal_or_worse_brier": "dm_reject_equal_or_worse_brier",
        }
    )
    comparison = result_frame.merge(bootstrap_holm, on="configuration", how="left").merge(dm_holm, on="configuration", how="left")
    comparison["inference_methods_agree"] = (
        comparison["bootstrap_reject_equal_or_worse_brier"] == comparison["dm_reject_equal_or_worse_brier"]
    )
    comparison["both_methods_support_candidate"] = (
        comparison["bootstrap_reject_equal_or_worse_brier"]
        & comparison["dm_reject_equal_or_worse_brier"]
        & (comparison["ci95_upper"] < 0)
    )
    return comparison.sort_values("configuration", ignore_index=True)
