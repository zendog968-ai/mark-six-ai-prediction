import unittest

import pandas as pd

from colour_analysis import build_colour_analysis, colour_analysis_payload, recommendation_colour_metadata


class ColourAnalysisTests(unittest.TestCase):
    @staticmethod
    def _draws() -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"Draw": 26001, "Date": "2026-01-01", "N1": 1, "N2": 3, "N3": 5, "N4": 7, "N5": 9, "N6": 11, "Special": 49},
                {"Draw": 26002, "Date": "2026-01-03", "N1": 2, "N2": 4, "N3": 6, "N4": 8, "N5": 10, "N6": 12, "Special": 13},
            ]
        )

    def test_state_derives_main_and_special_colour_data_without_mutating_source(self) -> None:
        draws = self._draws()
        state = build_colour_analysis(draws, windows=(1, 2))
        self.assertEqual(list(draws.columns), ["Draw", "Date", "N1", "N2", "N3", "N4", "N5", "N6", "Special"])
        self.assertEqual(state["draw_count"], 2)
        self.assertEqual(state["latest_draw"]["正選球色組成"], "紅色 3、藍色 2、綠色 1")
        self.assertEqual(state["latest_draw"]["特別號球色"], "紅色")
        self.assertEqual(len(state["window_table"]), 6)

    def test_json_payload_and_recommendation_metadata_are_serializable(self) -> None:
        payload = colour_analysis_payload(self._draws())
        self.assertEqual(payload["mapping_group_sizes"], {"紅色": 17, "藍色": 16, "綠色": 16})
        self.assertIn("固定號碼標籤", payload["interpretation"])
        metadata = recommendation_colour_metadata([1, 3, 5, 7, 9, 11], 49)
        self.assertEqual(metadata["main_colour_counts"], {"red": 2, "blue": 2, "green": 2})
        self.assertEqual(metadata["special_number_colour"], "green")
