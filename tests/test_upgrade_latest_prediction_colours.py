import json
import tempfile
import unittest
from pathlib import Path

from lotto_data import generate_mock_data
from scripts.upgrade_latest_prediction_colours import upgrade_latest_prediction_colours


class UpgradeLatestPredictionColoursTests(unittest.TestCase):
    def test_upgrade_preserves_operational_fields_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_path = root / "history.csv"
            output_path = root / "latest_prediction.json"
            generate_mock_data(60).to_csv(history_path, index=False)
            original = {
                "latest_draw": {"draw": 26093},
                "prediction_log": {"target_draw": 26094, "logged": False},
                "blind_test_log": {"target_draw": 26094, "locked": True},
                "four_config_brier_log": {"target_draw": 26094, "locked": True},
                "top_weights": [{"number": 37, "relative_weight": 0.4}],
                "top_5_recommendations": [
                    {"set_index": 1, "numbers": [1, 3, 5, 7, 9, 11], "special_number": 49, "recommendation_format": "6+1"},
                    {"set_index": 2, "numbers": [2, 4, 6, 8, 10, 12], "recommendation_format": "6"},
                ],
                "model": {"name": "existing"},
            }
            output_path.write_text(json.dumps(original), encoding="utf-8")
            upgraded, changed = upgrade_latest_prediction_colours(history_path, output_path)
            self.assertTrue(changed)
            self.assertEqual(upgraded["prediction_log"], original["prediction_log"])
            self.assertEqual(upgraded["blind_test_log"], original["blind_test_log"])
            self.assertEqual(upgraded["four_config_brier_log"], original["four_config_brier_log"])
            self.assertEqual(upgraded["top_weights"][0]["ball_colour"], "blue")
            self.assertEqual(upgraded["top_5_recommendations"][0]["special_number_colour"], "green")
            self.assertEqual(sum(upgraded["top_5_recommendations"][0]["main_colour_counts"].values()), 6)
            self.assertIn("colour_analysis", upgraded)
            again, changed_again = upgrade_latest_prediction_colours(history_path, output_path)
            self.assertFalse(changed_again)
            self.assertEqual(again, upgraded)
