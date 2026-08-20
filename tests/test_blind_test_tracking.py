import tempfile
import unittest
from pathlib import Path

from blind_test_tracking import (
    BLIND_TEST_CONFIG_VERSION,
    blind_test_metrics,
    build_blind_test_table,
    load_blind_test_history,
    record_blind_test,
)
from lotto_data import generate_mock_data


class BlindTestTrackingTests(unittest.TestCase):
    def test_locks_three_variants_once_and_settles_against_later_actual_draw(self):
        all_draws = generate_mock_data(61)
        history = all_draws.iloc[:60]
        source = history.iloc[-1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blind_test_history.json"
            record, created = record_blind_test(history, int(source["Draw"]), str(source["Date"]), path)
            duplicate, duplicate_created = record_blind_test(history, int(source["Draw"]), str(source["Date"]), path)

            self.assertTrue(created)
            self.assertFalse(duplicate_created)
            self.assertEqual(record, duplicate)
            self.assertEqual(record["target_draw"], 61)
            self.assertEqual(record["config_version"], BLIND_TEST_CONFIG_VERSION)
            self.assertEqual([variant["key"] for variant in record["variants"]], ["fusion_top6", "frequency50_50", "hot6"])
            self.assertTrue(all(len(variant["numbers"]) == 6 for variant in record["variants"]))
            self.assertEqual(len(load_blind_test_history(path)), 1)

            table, error = build_blind_test_table(all_draws, [record])
            self.assertIsNone(error)
            self.assertEqual(len(table), 3)
            self.assertTrue((table["狀態"] == "已結算").all())
            self.assertTrue((table["紀錄完整性"] == "通過").all())
            metrics = blind_test_metrics(table)
            self.assertEqual(metrics["locked_records"], 1)
            self.assertEqual(metrics["settled_records"], 1)
            self.assertEqual(metrics["settled_variants"], 3)

    def test_tampered_existing_record_is_not_overwritten(self):
        history = generate_mock_data(60)
        source = history.iloc[-1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blind_test_history.json"
            record, _created = record_blind_test(history, int(source["Draw"]), str(source["Date"]), path)
            record["variants"][0]["numbers"] = [1, 2, 3, 4, 5, 6]
            path.write_text('{"blind_tests": [' + __import__("json").dumps(record, ensure_ascii=False) + "]}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "雜湊不符"):
                record_blind_test(history, int(source["Draw"]), str(source["Date"]), path)
