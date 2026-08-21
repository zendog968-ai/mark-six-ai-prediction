import numpy as np
import pandas as pd
import pytest

from brier_significance import (
    brier_score_per_draw,
    circular_moving_block_bootstrap_mean,
    compare_configurations,
    diebold_mariano_test,
    holm_bonferroni,
)


def test_brier_score_per_draw_handles_main_numbers_only():
    probabilities = np.full((1, 49), 6 / 49)
    score = brier_score_per_draw(probabilities, [[1, 2, 3, 4, 5, 6]])
    assert score.shape == (1,)
    assert score[0] == pytest.approx(0.10745522698875466)


def test_bootstrap_returns_negative_interval_for_uniformly_better_candidate():
    differences = np.linspace(-0.03, -0.01, 80)
    result = circular_moving_block_bootstrap_mean(differences, block_length=5, n_bootstrap=500, seed=7)
    assert result.mean_difference < 0
    assert result.ci95_upper < 0
    assert result.p_value_one_sided < 0.01


def test_diebold_mariano_returns_one_sided_support_for_uniformly_better_candidate():
    differences = np.linspace(-0.03, -0.01, 80)
    result = diebold_mariano_test(differences, forecast_horizon=1, truncation_lag=5)
    assert result.mean_difference < 0
    assert result.dm_statistic < 0
    assert result.p_value_one_sided < 0.05


def test_holm_bonferroni_has_monotonic_adjusted_values():
    result = holm_bonferroni({"a": 0.01, "b": 0.03, "c": 0.20})
    indexed = result.set_index("configuration")
    assert indexed.loc["a", "p_value_holm"] == pytest.approx(0.03)
    assert indexed.loc["b", "p_value_holm"] == pytest.approx(0.06)
    assert indexed.loc["c", "p_value_holm"] == pytest.approx(0.20)
    assert bool(indexed.loc["a", "reject_equal_or_worse_brier"])
    assert not bool(indexed.loc["b", "reject_equal_or_worse_brier"])


def test_compare_configurations_uses_same_common_draws_and_rejects_duplicate_draws():
    frame = pd.DataFrame(
        {
            "Draw": list(range(1, 41)),
            "baseline": np.linspace(0.11, 0.12, 40),
            "candidate_a": np.linspace(0.10, 0.11, 40),
            "candidate_b": np.linspace(0.111, 0.121, 40),
        }
    )
    result = compare_configurations(frame, baseline="baseline", candidates=["candidate_a", "candidate_b"], n_bootstrap=500)
    assert set(result["configuration"]) == {"candidate_a", "candidate_b"}
    assert set(result["n_draws"]) == {40}
    assert {"bootstrap_p_value_holm", "dm_p_value_holm", "inference_methods_agree"}.issubset(result.columns)
    with pytest.raises(ValueError, match="每個期數"):
        compare_configurations(pd.concat([frame, frame.iloc[[0]]]), baseline="baseline", candidates=["candidate_a"], n_bootstrap=500)
