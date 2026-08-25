import tempfile
import unittest
from pathlib import Path

from lotto_data import generate_mock_data
from scripts.rebuild_latest_prediction_format import LOCAL_HISTORY_SOURCE, rebuild_latest_prediction


class RebuildLatestPredictionFormatTests(unittest.TestCase):
    def test_rebuild_writes_six_plus_one_without_other_ledgers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_path = root / "history.csv"
            output_path = root / "latest_prediction.json"
            generate_mock_data(60).to_csv(history_path, index=False)
            payload = rebuild_latest_prediction(history_path, output_path)
            first = payload["top_5_recommendations"][0]
            self.assertTrue(output_path.exists())
            self.assertEqual(payload["latest_draw"]["source_url"], LOCAL_HISTORY_SOURCE)
            self.assertEqual(first["recommendation_format"], "6+1")
            self.assertNotIn(first["special_number"], first["numbers"])
            self.assertTrue(all(item["recommendation_format"] == "6" for item in payload["top_5_recommendations"][1:]))


if __name__ == "__main__":
    unittest.main()
