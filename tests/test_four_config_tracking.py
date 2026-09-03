import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from four_config_tracking import FOUR_CONFIG_VERSION, _record_hash, load_four_config_history, record_four_config


def _record(target_draw: int, *, version: str = FOUR_CONFIG_VERSION) -> dict:
    record = {
        "experiment_id": "marksix_four_configuration_brier_tracking",
        "config_version": version,
        "target_draw": target_draw,
        "target_date": "2026-08-30",
        "locked_at_utc": "2026-08-27T14:00:00+00:00",
        "source_latest_draw": target_draw - 1,
        "source_latest_date": "2026-08-27",
        "source_history_records": 600,
        "source_history_sha256": "source-hash",
        "configuration_probabilities": {key: [6.0 / 49.0] * 49 for key in ("fusion_top6", "frequency50_50", "hot6", "multiscale_calibrated")},
        "variants": [],
        "status": "locked_pending_result",
        "purpose": "test-only locked record",
    }
    record["record_sha256"] = _record_hash(record)
    return record


class FourConfigurationTrackingTests(unittest.TestCase):
    def test_same_target_returns_existing_immutable_record_without_rebuilding(self):
        proposed = _record(26095)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "brier_tracking_history.json"
            with patch("four_config_tracking.build_four_config_record", return_value=proposed) as builder:
                first, created = record_four_config(pd.DataFrame(), 26094, "2026-08-27", path)
                duplicate, created_again = record_four_config(pd.DataFrame(), 26094, "2026-08-27", path)
            loaded = load_four_config_history(path)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first, duplicate)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(builder.call_count, 1)

    def test_tampered_existing_vector_refuses_overwrite(self):
        record = _record(26095)
        record["configuration_probabilities"]["fusion_top6"][0] = 0.9
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "brier_tracking_history.json"
            path.write_text(json.dumps({"records": [record]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "雜湊不符"):
                record_four_config(pd.DataFrame(), 26094, "2026-08-27", path)

    def test_other_configuration_version_refuses_overwrite(self):
        record = _record(26095, version="other-version")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "brier_tracking_history.json"
            path.write_text(json.dumps({"records": [record]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "其他配置版本"):
                record_four_config(pd.DataFrame(), 26094, "2026-08-27", path)
