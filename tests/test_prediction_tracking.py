import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from prediction_tracking import (
    build_hit_rate_table,
    build_prediction_record,
    hit_rate_metrics,
    load_prediction_history,
    record_prediction,
)


def sample_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            [26089, "2026-08-15", 4, 16, 25, 27, 28, 33, 14],
            [26090, "2026-08-18", 1, 9, 14, 33, 40, 48, 7],
        ],
        columns=["Draw", "Date", "N1", "N2", "N3", "N4", "N5", "N6", "Special"],
    )


def sample_payload() -> dict:
    return {
        "model": {"name": "Random Forest + XGBoost Ensemble", "features": ["frequency_50"], "fusion": {"random_forest_weight": 0.5, "xgboost_weight": 0.5}, "kmeans_clusters": 4},
        "top_5_recommendations": [
            {"set_index": 1, "numbers": [1, 9, 14, 33, 40, 48], "special_number": 7, "recommendation_format": "6+1", "odd_count": 3, "number_sum": 145, "consecutive_pairs": 0},
            {"set_index": 2, "numbers": [2, 3, 5, 6, 8, 10], "odd_count": 3, "number_sum": 34, "consecutive_pairs": 0},
            {"set_index": 3, "numbers": [11, 12, 13, 15, 17, 19], "odd_count": 5, "number_sum": 87, "consecutive_pairs": 2},
            {"set_index": 4, "numbers": [20, 21, 22, 23, 24, 25], "odd_count": 3, "number_sum": 135, "consecutive_pairs": 5},
            {"set_index": 5, "numbers": [26, 27, 28, 29, 30, 31], "odd_count": 3, "number_sum": 171, "consecutive_pairs": 5},
        ],
    }


class PredictionTrackingTests(unittest.TestCase):
    def test_record_is_saved_once_per_target_draw(self):
        history = sample_history().iloc[:1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction_history.json"
            record, created = record_prediction(history, 26089, "2026-08-15", sample_payload(), path)
            duplicate, duplicate_created = record_prediction(history, 26089, "2026-08-15", sample_payload(), path)
            self.assertTrue(created)
            self.assertFalse(duplicate_created)
            self.assertEqual(record["target_draw"], 26090)
            self.assertEqual(record["combinations"][0]["recommendation_format"], "6+1")
            self.assertEqual(record["combinations"][0]["special_number"], 7)
            self.assertEqual(record["combinations"][0]["special_number_colour"], "red")
            self.assertEqual(sum(record["combinations"][0]["main_colour_counts"].values()), 6)
            self.assertTrue(all("special_number" not in item for item in record["combinations"][1:]))
            self.assertEqual(record, duplicate)
            self.assertEqual(len(load_prediction_history(path)), 1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 2)

    def test_hit_table_marks_actual_intersections_and_metrics(self):
        history = sample_history()
        record = build_prediction_record(history.iloc[:1], 26089, "2026-08-15", sample_payload())
        table, error = build_hit_rate_table(history, [record])
        self.assertIsNone(error)
        self.assertEqual(table.iloc[0]["狀態"], "已結算")
        self.assertEqual(table.iloc[0]["單期最高命中"], 6)
        self.assertIn("✅01", table.iloc[0]["命中號碼"])
        self.assertIn("組1（6+1）", table.iloc[0]["AI 預測 5 組組合"])
        self.assertIn("[特別號碼：07]", table.iloc[0]["AI 預測 5 組組合"])
        metrics = hit_rate_metrics(table)
        self.assertEqual(metrics["settled_draws"], 1)
        self.assertEqual(metrics["draws_with_3_plus"], 1)
        self.assertEqual(metrics["average_best_hits"], 6.0)

    def test_first_special_number_must_be_distinct_from_main_numbers(self):
        payload = sample_payload()
        payload["top_5_recommendations"][0]["special_number"] = 1
        with self.assertRaisesRegex(ValueError, "不可與六個主號重複"):
            build_prediction_record(sample_history().iloc[:1], 26089, "2026-08-15", payload)


if __name__ == "__main__":
    unittest.main()
