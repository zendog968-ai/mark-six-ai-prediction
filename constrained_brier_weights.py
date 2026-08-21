"""Constrained Brier-optimal ensemble weights for pre-registered forecasts.

This module proposes weights only.  A caller must first confirm the external
Bootstrap, Diebold--Mariano, Holm, effect-size, and sample-size gates.  The
result must be frozen for a future out-of-sample period before activation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class WeightUpdateProposal:
    approved: bool
    reason: str
    current_weights: list[float]
    target_weights: list[float]
    proposed_weights: list[float]
    objective_at_current: float | None
    objective_at_target: float | None
    mean_brier_at_current: float | None
    mean_brier_at_target: float | None
    iterations: int
    alpha: float
    shrinkage: float
    lower_bound: float
    upper_bound: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def project_bounded_simplex(
    values: Iterable[float],
    *,
    lower_bound: float = 0.10,
    upper_bound: float = 0.55,
    tolerance: float = 1e-12,
) -> np.ndarray:
    """Project a vector onto weights that sum to one within uniform bounds."""
    vector = np.asarray(list(values), dtype=float)
    if vector.ndim != 1 or vector.size < 2 or not np.isfinite(vector).all():
        raise ValueError("權重必須是一維、至少兩項且為有限數值。")
    if not 0 <= lower_bound <= upper_bound <= 1:
        raise ValueError("權重邊界必須符合 0 ≤ lower ≤ upper ≤ 1。")
    n_models = vector.size
    if lower_bound * n_models > 1 + tolerance or upper_bound * n_models < 1 - tolerance:
        raise ValueError("給定的權重邊界無法形成總和為 1 的組合。")
    low = float(np.min(vector - upper_bound))
    high = float(np.max(vector - lower_bound))
    for _ in range(200):
        threshold = (low + high) / 2.0
        projected = np.clip(vector - threshold, lower_bound, upper_bound)
        if projected.sum() > 1:
            low = threshold
        else:
            high = threshold
        if high - low <= tolerance:
            break
    projected = np.clip(vector - (low + high) / 2.0, lower_bound, upper_bound)
    # The bisection result is accurate to tolerance; distribute only residual
    # numerical noise across still-free entries without breaching bounds.
    residual = 1.0 - float(projected.sum())
    free = (projected > lower_bound + tolerance) & (projected < upper_bound - tolerance)
    if abs(residual) > tolerance and free.any():
        projected[free] += residual / int(free.sum())
    if not np.isclose(projected.sum(), 1.0, atol=1e-9):
        raise RuntimeError("單純形投影未能達成權重總和為 1。")
    return projected


def _validate_probability_panel(probabilities: np.ndarray, outcomes: np.ndarray) -> tuple[int, int]:
    if probabilities.ndim != 3 or probabilities.shape[2] != 49:
        raise ValueError("probabilities 必須是 (共同期數, 配置數, 49) 的三維陣列。")
    if outcomes.shape != (probabilities.shape[0], 49):
        raise ValueError("outcomes 必須是 (共同期數, 49)，且與 probabilities 的共同期數相同。")
    if probabilities.shape[0] < 1 or probabilities.shape[1] < 2:
        raise ValueError("至少需要一個共同期數及兩個配置。")
    if not np.isfinite(probabilities).all() or not np.isfinite(outcomes).all():
        raise ValueError("機率與結果不得包含 NaN 或無限值。")
    if (probabilities < 0).any() or (probabilities > 1).any():
        raise ValueError("每個號碼機率必須位於 0 至 1。")
    if not np.all(np.isin(outcomes, (0, 1))):
        raise ValueError("outcomes 必須為 0/1 結果向量。")
    if not np.all(outcomes.sum(axis=1) == 6):
        raise ValueError("每期 outcomes 必須恰有六個正選。")
    if not np.allclose(probabilities.sum(axis=2), 6.0, atol=1e-6):
        raise ValueError("每期每個配置的 49 號機率總和必須為 6。")
    return probabilities.shape[0], probabilities.shape[1]


def ensemble_brier_objective(
    weights: Iterable[float],
    probabilities: np.ndarray,
    outcomes: np.ndarray,
    *,
    shrinkage: float = 0.05,
) -> tuple[float, float]:
    """Return regularised objective and unpenalised mean Brier score."""
    panel = np.asarray(probabilities, dtype=float)
    actual = np.asarray(outcomes, dtype=float)
    _n_draws, n_models = _validate_probability_panel(panel, actual)
    vector = np.asarray(list(weights), dtype=float)
    if vector.shape != (n_models,) or not np.isfinite(vector).all():
        raise ValueError("weights 維度必須與配置數相同，且皆為有限數值。")
    if shrinkage < 0:
        raise ValueError("shrinkage 不可為負數。")
    mixture = np.einsum("tkj,k->tj", panel, vector)
    mean_brier = float(np.mean((mixture - actual) ** 2))
    equal_weight = 1.0 / n_models
    objective = mean_brier + float(shrinkage) * float(np.sum((vector - equal_weight) ** 2))
    return objective, mean_brier


def optimize_constrained_brier_weights(
    probabilities: np.ndarray,
    outcomes: np.ndarray,
    *,
    lower_bound: float = 0.10,
    upper_bound: float = 0.55,
    shrinkage: float = 0.05,
    learning_rate: float = 0.50,
    max_iterations: int = 5_000,
    tolerance: float = 1e-10,
    initial_weights: Iterable[float] | None = None,
) -> tuple[np.ndarray, int]:
    """Use projected gradient descent to minimise regularised mean Brier error."""
    panel = np.asarray(probabilities, dtype=float)
    actual = np.asarray(outcomes, dtype=float)
    n_draws, n_models = _validate_probability_panel(panel, actual)
    if shrinkage < 0 or learning_rate <= 0 or max_iterations < 1 or tolerance <= 0:
        raise ValueError("最佳化參數必須為正數，shrinkage 可為零。")
    if initial_weights is None:
        weights = project_bounded_simplex(np.full(n_models, 1.0 / n_models), lower_bound=lower_bound, upper_bound=upper_bound)
    else:
        weights = project_bounded_simplex(initial_weights, lower_bound=lower_bound, upper_bound=upper_bound)
    equal_weight = 1.0 / n_models
    for iteration in range(1, max_iterations + 1):
        mixture = np.einsum("tkj,k->tj", panel, weights)
        gradient = (2.0 / (n_draws * 49.0)) * np.einsum("tkj,tj->k", panel, mixture - actual)
        gradient += 2.0 * shrinkage * (weights - equal_weight)
        candidate = project_bounded_simplex(weights - learning_rate * gradient, lower_bound=lower_bound, upper_bound=upper_bound)
        if np.max(np.abs(candidate - weights)) <= tolerance:
            return candidate, iteration
        weights = candidate
    return weights, max_iterations


def smooth_weight_transition(
    current_weights: Iterable[float],
    target_weights: Iterable[float],
    *,
    alpha: float = 0.25,
    lower_bound: float = 0.10,
    upper_bound: float = 0.55,
) -> np.ndarray:
    """Apply a bounded convex transition; alpha=0.25 adopts one quarter of a move."""
    if not 0 < alpha <= 1:
        raise ValueError("alpha 必須介於 0（不含）與 1（含）之間。")
    current = project_bounded_simplex(current_weights, lower_bound=lower_bound, upper_bound=upper_bound)
    target = project_bounded_simplex(target_weights, lower_bound=lower_bound, upper_bound=upper_bound)
    return project_bounded_simplex((1.0 - alpha) * current + alpha * target, lower_bound=lower_bound, upper_bound=upper_bound)


def propose_weight_update(
    probabilities: np.ndarray,
    outcomes: np.ndarray,
    current_weights: Iterable[float],
    *,
    qualification_passed: bool,
    qualification_reason: str,
    alpha: float = 0.25,
    lower_bound: float = 0.10,
    upper_bound: float = 0.55,
    shrinkage: float = 0.05,
) -> WeightUpdateProposal:
    """Produce a candidate update only after an external statistical gate passes.

    The caller must derive ``qualification_passed`` from the pre-registered
    100-draw Bootstrap/DM/Holm/effect-size policy.  This function deliberately
    does not inspect p-values itself, preventing accidental policy drift.
    """
    panel = np.asarray(probabilities, dtype=float)
    actual = np.asarray(outcomes, dtype=float)
    _n_draws, n_models = _validate_probability_panel(panel, actual)
    current = project_bounded_simplex(current_weights, lower_bound=lower_bound, upper_bound=upper_bound)
    current_objective, current_brier = ensemble_brier_objective(current, panel, actual, shrinkage=shrinkage)
    if not qualification_passed:
        return WeightUpdateProposal(
            approved=False,
            reason=f"未進入權重最佳化：{qualification_reason}",
            current_weights=current.tolist(), target_weights=current.tolist(), proposed_weights=current.tolist(),
            objective_at_current=current_objective, objective_at_target=current_objective,
            mean_brier_at_current=current_brier, mean_brier_at_target=current_brier,
            iterations=0, alpha=alpha, shrinkage=shrinkage, lower_bound=lower_bound, upper_bound=upper_bound,
        )
    target, iterations = optimize_constrained_brier_weights(
        panel, actual, lower_bound=lower_bound, upper_bound=upper_bound, shrinkage=shrinkage, initial_weights=current
    )
    target_objective, target_brier = ensemble_brier_objective(target, panel, actual, shrinkage=shrinkage)
    proposed = smooth_weight_transition(current, target, alpha=alpha, lower_bound=lower_bound, upper_bound=upper_bound)
    return WeightUpdateProposal(
        approved=True,
        reason=f"統計資格閘門已通過：{qualification_reason}。候選權重必須先凍結作未來樣本外盲測。",
        current_weights=current.tolist(), target_weights=target.tolist(), proposed_weights=proposed.tolist(),
        objective_at_current=current_objective, objective_at_target=target_objective,
        mean_brier_at_current=current_brier, mean_brier_at_target=target_brier,
        iterations=iterations, alpha=alpha, shrinkage=shrinkage, lower_bound=lower_bound, upper_bound=upper_bound,
    )
