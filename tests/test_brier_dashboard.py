import numpy as np

from brier_dashboard import build_brier_by_draw, cumulative_brier, run_four_configuration_inference


def _probabilities(seed: int):
    values = np.full(49, 6 / 49, dtype=float)
    values[seed % 49] += 0.005
    values -= 0.005 / 48
    return values.tolist()


def test_builds_common_brier_rows_only_when_all_four_vectors_are_locked():
    complete = {
        "target_draw": 26092,
        "target_date": "2026-08-22",
        "actual_main_numbers": [1, 2, 3, 4, 5, 6],
        "configuration_probabilities": {
            "fusion_top6": _probabilities(1),
            "frequency50_50": _probabilities(2),
            "hot6": _probabilities(3),
            "multiscale_calibrated": _probabilities(4),
        },
    }
    incomplete = {"target_draw": 26093, "actual_main_numbers": [1, 2, 3, 4, 5, 6], "configuration_probabilities": {}}
    frame, warnings = build_brier_by_draw([complete, incomplete])
    assert frame["Draw"].tolist() == [26092]
    assert len(warnings) == 1
    assert len(cumulative_brier(frame)) == 4


def test_inference_waits_for_at_least_three_common_draws():
    frame, _warnings = build_brier_by_draw([])
    result, message = run_four_configuration_inference(frame, block_length=5, n_bootstrap=100)
    assert result.empty
    assert message is not None


def test_pending_locked_record_is_reported_as_waiting_for_official_result():
    record = {
        "target_draw": 26092,
        "configuration_probabilities": {
            "fusion_top6": _probabilities(1),
            "frequency50_50": _probabilities(2),
            "hot6": _probabilities(3),
            "multiscale_calibrated": _probabilities(4),
        },
    }
    frame, warnings = build_brier_by_draw([record])
    assert frame.empty
    assert "等待官方正選結果結算" in warnings[0]
