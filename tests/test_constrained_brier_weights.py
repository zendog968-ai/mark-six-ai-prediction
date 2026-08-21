import numpy as np

from constrained_brier_weights import (
    project_bounded_simplex,
    propose_weight_update,
    smooth_weight_transition,
)


def _controlled_panel():
    outcomes = np.zeros((3, 49), dtype=float)
    outcomes[:, :6] = 1.0
    good = np.full(49, 3.0 / 43.0)
    good[:6] = 0.5
    poor = np.full(49, 5.88 / 43.0)
    poor[:6] = 0.02
    middle = (good + poor) / 2.0
    panel = np.stack([good, poor, middle, poor], axis=0)
    return np.repeat(panel[None, :, :], 3, axis=0), outcomes


def test_projection_obeys_bounds_and_total():
    projected = project_bounded_simplex([10.0, -5.0, 0.2, 0.1])
    assert np.isclose(projected.sum(), 1.0)
    assert (projected >= 0.10 - 1e-10).all()
    assert (projected <= 0.55 + 1e-10).all()


def test_qualification_gate_prevents_any_change():
    probabilities, outcomes = _controlled_panel()
    proposal = propose_weight_update(probabilities, outcomes, [0.25] * 4, qualification_passed=False, qualification_reason="Holm 未通過")
    assert not proposal.approved
    assert proposal.proposed_weights == proposal.current_weights


def test_smoothed_update_moves_only_one_quarter_toward_target():
    probabilities, outcomes = _controlled_panel()
    proposal = propose_weight_update(probabilities, outcomes, [0.25] * 4, qualification_passed=True, qualification_reason="雙方法一致")
    current = np.asarray(proposal.current_weights)
    target = np.asarray(proposal.target_weights)
    proposed = np.asarray(proposal.proposed_weights)
    assert proposal.approved
    assert np.allclose(proposed, smooth_weight_transition(current, target, alpha=0.25))
    assert proposed[0] > current[0]
    assert np.isclose(proposed.sum(), 1.0)
