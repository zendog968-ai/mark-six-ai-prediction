import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from lotto_data import REQUIRED_COLUMNS, generate_mock_data
from updater import (
    FALLBACK_RESULTS_URL,
    DrawResult,
    append_if_new,
    load_history,
    parse_lotteryextreme_results,
    update,
)


FALLBACK_SAMPLE = """
<table>
  <tr class='cy'><td class='cx'>15/08/2026 Saturday (26/089) Winners</td></tr>
  <tr><td><ul class='displayball'><li>4<li>16<li>25<li>27<li>28<li>33<li class='dbx'> <li>14</ul></td></tr>
</table>
"""


class UpdaterTests(unittest.TestCase):
    def test_fallback_parser_extracts_one_complete_valid_draw(self):
        draws = parse_lotteryextreme_results(FALLBACK_SAMPLE)
        self.assertEqual(len(draws), 1)
        self.assertEqual(draws[0].draw, 26089)
        self.assertEqual(draws[0].main_numbers, (4, 16, 25, 27, 28, 33))
        self.assertEqual(draws[0].special, 14)

    def test_append_if_new_rejects_existing_draw_without_duplication(self):
        history = generate_mock_data(60)
        latest = DrawResult(int(history.iloc[-1]["Draw"]), "2026-08-15", (4, 16, 25, 27, 28, 33), 14, FALLBACK_RESULTS_URL)
        combined, appended = append_if_new(history, latest)
        self.assertFalse(appended)
        self.assertEqual(len(combined), len(history))

    def test_update_converts_legacy_csv_appends_once_and_writes_prediction_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = generate_mock_data(60).rename(
                columns={"Draw": "draw_no", "Date": "draw_date", "N1": "main_1", "N2": "main_2", "N3": "main_3", "N4": "main_4", "N5": "main_5", "N6": "main_6", "Special": "special"}
            )
            history_path = root / "history.csv"
            output_path = root / "latest_prediction.json"
            blind_path = root / "blind_test_history.json"
            legacy.to_csv(history_path, index=False)

            def fake_fetcher(url):
                self.assertIn(url, {"https://bet.hkjc.com/en/marksix/results", FALLBACK_RESULTS_URL})
                return FALLBACK_SAMPLE if url == FALLBACK_RESULTS_URL else "no parseable official result"

            payload = update(history_path, output_path, fetcher=fake_fetcher, blind_test_history_path=blind_path)
            written = load_history(history_path)
            self.assertEqual(list(written.columns), list(REQUIRED_COLUMNS))
            self.assertEqual(len(written), 61)
            self.assertTrue(payload["latest_draw"]["appended_to_history"])
            self.assertEqual(len(payload["top_5_recommendations"]), 5)
            first_recommendation = payload["top_5_recommendations"][0]
            self.assertEqual(first_recommendation["recommendation_format"], "6+1")
            self.assertNotIn(first_recommendation["special_number"], first_recommendation["numbers"])
            self.assertTrue(1 <= first_recommendation["special_number"] <= 49)
            self.assertIn(first_recommendation["special_number_colour"], {"red", "blue", "green"})
            self.assertEqual(sum(first_recommendation["main_colour_counts"].values()), 6)
            self.assertTrue(all(item["recommendation_format"] == "6" and "special_number" not in item for item in payload["top_5_recommendations"][1:]))
            self.assertTrue(all(sum(item["main_colour_counts"].values()) == 6 for item in payload["top_5_recommendations"]))
            strengths = [item["relative_strength_percent"] for item in payload["top_5_recommendations"]]
            self.assertEqual(strengths[0], 100)
            self.assertTrue(all(isinstance(value, int) and 0 <= value <= 100 for value in strengths))
            self.assertTrue(all(item["strength_label"].startswith("相對推薦強度 ") for item in payload["top_5_recommendations"]))
            self.assertEqual(len(payload["top_weights"]), 25)
            self.assertEqual(payload["model"]["name"], "Random Forest + XGBoost Ensemble")
            self.assertIn("kmeans_cluster", payload["model"]["features"])
            self.assertIn("xgboost_weight", payload["top_weights"][0])
            self.assertIn("kmeans_cluster", payload["top_weights"][0])
            self.assertIn(payload["top_weights"][0]["ball_colour"], {"red", "blue", "green"})
            self.assertIn("colour_analysis", payload)
            self.assertEqual(payload["colour_analysis"]["mapping_group_sizes"], {"紅色": 17, "藍色": 16, "綠色": 16})
            self.assertIn("紅藍綠", payload["model"]["research_context"]["ball_colours"])
            self.assertNotIn("ball_colour", payload["model"]["features"])
            self.assertEqual(payload["blind_test_log"]["target_draw"], 26090)
            self.assertTrue(payload["blind_test_log"]["locked"])
            self.assertTrue(blind_path.exists())
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["history_records"], 61)
            first_json = output_path.read_text(encoding="utf-8")
            repeated = update(history_path, output_path, fetcher=fake_fetcher, blind_test_history_path=blind_path)
            self.assertFalse(repeated["run_appended_to_history"])
            self.assertEqual(len(load_history(history_path)), 61)
            self.assertEqual(output_path.read_text(encoding="utf-8"), first_json)

            stale = json.loads(first_json)
            stale["history_records"] = 1_000
            stale.pop("colour_analysis")
            stale["top_5_recommendations"][0].pop("special_number_colour")
            output_path.write_text(json.dumps(stale), encoding="utf-8")
            refreshed = update(history_path, output_path, fetcher=fake_fetcher, blind_test_history_path=blind_path)
            self.assertFalse(refreshed["run_appended_to_history"])
            self.assertEqual(refreshed["history_records"], 61)
            self.assertIn("colour_analysis", refreshed)
            self.assertIn("special_number_colour", refreshed["top_5_recommendations"][0])
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8"))["history_records"], 61)

    def test_update_records_four_configuration_lock_when_enabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history = generate_mock_data(60)
            history_path = root / "history.csv"
            extended_history_path = root / "extended.csv"
            output_path = root / "latest_prediction.json"
            blind_path = root / "blind_test_history.json"
            four_config_path = root / "brier_tracking_history.json"
            history.to_csv(history_path, index=False)
            history.to_csv(extended_history_path, index=False)

            def fake_fetcher(url):
                return FALLBACK_SAMPLE if url == FALLBACK_RESULTS_URL else "no parseable official result"

            locked_record = {
                "target_draw": 26090,
                "target_date": "2026-08-18",
                "config_version": "test-four-config-v1",
                "status": "locked_pending_result",
                "configuration_probabilities": {"fusion_top6": [6 / 49] * 49},
            }
            with patch("updater.record_four_config", return_value=(locked_record, True)) as recorder:
                payload = update(
                    history_path,
                    output_path,
                    fetcher=fake_fetcher,
                    blind_test_history_path=blind_path,
                    four_config_history_path=four_config_path,
                    extended_history_path=extended_history_path,
                    enable_four_config_tracking=True,
                )
            self.assertTrue(payload["four_config_brier_log"]["locked"])
            self.assertEqual(payload["four_config_brier_log"]["target_draw"], 26090)
            self.assertEqual(payload["four_config_brier_log"]["extended_history_records"], 61)
            recorder.assert_called_once()
            self.assertTrue(four_config_path.exists() is False)


if __name__ == "__main__":
    unittest.main()
