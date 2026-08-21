"""Standard-library smoke checks for brier_significance.py.

Run with: .venv/bin/python tests/smoke_brier_significance.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from brier_significance import (  # noqa: E402
    brier_score_per_draw,
    circular_moving_block_bootstrap_mean,
    compare_configurations,
    diebold_mariano_test,
    holm_bonferroni,
)


def main() -> None:
    uniform = np.full((1, 49), 6 / 49)
    score = brier_score_per_draw(uniform, [[1, 2, 3, 4, 5, 6]])[0]
    assert abs(score - 0.10745522698875466) < 1e-12

    bootstrap = circular_moving_block_bootstrap_mean(np.linspace(-0.03, -0.01, 80), block_length=5, n_bootstrap=500, seed=7)
    assert bootstrap.mean_difference < 0 and bootstrap.ci95_upper < 0 and bootstrap.p_value_one_sided < 0.01

    dm = diebold_mariano_test(np.linspace(-0.03, -0.01, 80), forecast_horizon=1, truncation_lag=5)
    assert dm.mean_difference < 0 and dm.dm_statistic < 0 and dm.p_value_one_sided < 0.05

    holm = holm_bonferroni({"a": 0.01, "b": 0.03, "c": 0.20}).set_index("configuration")
    assert abs(float(holm.loc["a", "p_value_holm"]) - 0.03) < 1e-12
    assert abs(float(holm.loc["b", "p_value_holm"]) - 0.06) < 1e-12
    assert bool(holm.loc["a", "reject_equal_or_worse_brier"])
    assert not bool(holm.loc["b", "reject_equal_or_worse_brier"])

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
    print("Brier significance smoke checks passed.")


if __name__ == "__main__":
    main()
