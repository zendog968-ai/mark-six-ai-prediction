from __future__ import annotations

import hashlib
import json
import unittest

from target_date_correction import correct_prediction_payload, correct_target_record


class TargetDateCorrectionTests(unittest.TestCase):
    @staticmethod
    def record_hash(record: dict) -> str:
        source = {key: value for key, value in record.items() if key != "record_sha256"}
        canonical = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def test_record_changes_only_target_date_and_dependent_hash(self):
        original = {
            "target_draw": 26096,
            "target_date": "2026-09-01",
            "status": "locked_pending_result",
            "combinations": [[7, 8, 9, 12, 17, 27]],
            "configuration_probabilities": {"fusion": [1 / 49] * 49},
            "actual_main_numbers": None,
            "locked_at_utc": "2026-08-30T00:00:00+00:00",
        }
        original["record_sha256"] = self.record_hash(original)
        corrected = correct_target_record(original, "2026-09-05", self.record_hash)
        self.assertEqual(corrected["target_date"], "2026-09-05")
        self.assertEqual(corrected["target_draw"], original["target_draw"])
        self.assertEqual(corrected["combinations"], original["combinations"])
        self.assertEqual(corrected["configuration_probabilities"], original["configuration_probabilities"])
        self.assertEqual(corrected["actual_main_numbers"], original["actual_main_numbers"])
        self.assertEqual(corrected["locked_at_utc"], original["locked_at_utc"])
        self.assertNotEqual(corrected["record_sha256"], original["record_sha256"])
        self.assertEqual(corrected["record_sha256"], self.record_hash(corrected))
        self.assertEqual(original["target_date"], "2026-09-01")

    def test_prediction_payload_corrects_matching_top_level_and_log_dates(self):
        original = {
            "target_draw": 26096,
            "target_date": "2026-09-01",
            "top_5_recommendations": [{"numbers": [7, 8, 9, 12, 17, 27]}],
            "prediction_log": {"target_draw": 26096, "target_date": "2026-09-01", "logged": True},
            "blind_test_log": {"target_draw": 26096, "target_date": "2026-09-01", "locked": True},
            "four_config_brier_log": {"target_draw": 26096, "target_date": "2026-09-01", "locked": True},
            "latest_draw": {"draw": 26095, "date": "2026-08-29"},
        }
        corrected = correct_prediction_payload(original, 26096, "2026-09-05")
        self.assertEqual(corrected["target_date"], "2026-09-05")
        for key in ("prediction_log", "blind_test_log", "four_config_brier_log"):
            self.assertEqual(corrected[key]["target_date"], "2026-09-05")
        self.assertEqual(corrected["top_5_recommendations"], original["top_5_recommendations"])
        self.assertEqual(corrected["latest_draw"], original["latest_draw"])
        self.assertEqual(original["target_date"], "2026-09-01")


if __name__ == "__main__":
    unittest.main()
