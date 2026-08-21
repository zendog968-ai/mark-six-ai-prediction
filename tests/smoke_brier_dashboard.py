from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brier_dashboard import build_brier_by_draw, cumulative_brier, run_four_configuration_inference


def vector(offset):
    values = [6 / 49 for _ in range(49)]
    values[offset] += 0.005
    for index in range(49):
        if index != offset:
            values[index] -= 0.005 / 48
    return values


record = {
    "target_draw": 26092,
    "target_date": "2026-08-22",
    "actual_main_numbers": [1, 2, 3, 4, 5, 6],
    "configuration_probabilities": {
        "fusion_top6": vector(0),
        "frequency50_50": vector(1),
        "hot6": vector(2),
        "multiscale_calibrated": vector(3),
    },
}
frame, warnings = build_brier_by_draw([record])
assert not warnings
assert frame["Draw"].tolist() == [26092]
assert len(cumulative_brier(frame)) == 4
results, message = run_four_configuration_inference(frame, block_length=5, n_bootstrap=100)
assert results.empty and message is not None
print("Brier dashboard smoke checks passed.")
