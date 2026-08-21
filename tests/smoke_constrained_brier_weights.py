from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from constrained_brier_weights import propose_weight_update


outcomes = np.zeros((3, 49), dtype=float)
outcomes[:, :6] = 1.0
good = np.full(49, 3.0 / 43.0)
good[:6] = 0.5
poor = np.full(49, 5.88 / 43.0)
poor[:6] = 0.02
probabilities = np.repeat(np.stack([good, poor, (good + poor) / 2.0, poor], axis=0)[None, :, :], 3, axis=0)

proposal = propose_weight_update(
    probabilities,
    outcomes,
    [0.25, 0.25, 0.25, 0.25],
    qualification_passed=True,
    qualification_reason="受控測試：外部統計閘門已通過",
)
assert proposal.approved
assert abs(sum(proposal.proposed_weights) - 1.0) < 1e-9
assert all(0.10 - 1e-9 <= weight <= 0.55 + 1e-9 for weight in proposal.proposed_weights)
assert proposal.proposed_weights[0] > proposal.current_weights[0]
print("Constrained Brier weight smoke checks passed.")
