import pandas as pd

from weight_monitor import build_weight_monitor_state


def test_empty_history_shows_equal_baseline_and_waiting_gate():
    frame = pd.DataFrame(columns=["Draw"])
    state = build_weight_monitor_state(frame, [])
    assert state["active_version"] == "baseline-equal-v1"
    assert state["completed_common_draws"] == 0
    assert state["next_gate_remaining"] == 100
    assert state["status"] == "累積共同盲測中"
    assert set(state["weight_rows"]["目前權重"]) == {0.25}
    assert state["gate_rows"]["目前"].dtype == object
    assert state["gate_rows"]["目前"].tolist()[0] == "0"


def test_valid_frozen_version_reports_progress_without_reoptimising():
    frame = pd.DataFrame({"Draw": list(range(1, 101))})
    records = [{
        "version": "ensemble-v1",
        "status": "frozen",
        "freeze_completed_draws": 8,
        "proposed_weights": {
            "fusion_top6": 0.40,
            "frequency50_50": 0.20,
            "hot6": 0.20,
            "multiscale_calibrated": 0.20,
        },
    }]
    state = build_weight_monitor_state(frame, records)
    assert state["active_version"] == "ensemble-v1"
    assert state["status"] == "凍結盲測中"
    assert state["freeze_completed_draws"] == 8
    assert state["next_gate_remaining"] == 0
