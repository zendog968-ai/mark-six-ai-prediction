from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from weight_monitor import build_weight_monitor_state


state = build_weight_monitor_state(pd.DataFrame(columns=["Draw"]), [])
assert state["active_version"] == "baseline-equal-v1"
assert state["next_gate_remaining"] == 100
assert len(state["weight_rows"]) == 4
print("Weight monitor smoke checks passed.")
