import unittest
from pathlib import Path

from long_window_research import build_long_window_research_state, filter_long_window_research


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LongWindowResearchTests(unittest.TestCase):
    def test_versioned_snapshot_builds_family_and_holdout_tables(self):
        state = build_long_window_research_state(
            PROJECT_ROOT / "data" / "long_window_research_snapshot.json"
        )

        self.assertTrue(state["available"])
        self.assertEqual(state["draw_count"], 3421)
        self.assertEqual(state["total_tests"], 1269)
        self.assertEqual(len(state["family_table"]), 5)
        self.assertEqual(len(state["holdout_table"]), 10)
        self.assertEqual(state["passed_holdout"], 0)
        self.assertIn("5期 Holm 顯著數", state["family_table"].columns)
        self.assertIn("10期 Holm 顯著數", state["family_table"].columns)
        self.assertIn("通過留出驗證", state["holdout_table"].columns)
        self.assertEqual(list(state["window_signal_chart"].index), ["5 期", "10 期"])
        self.assertEqual(state["window_signal_chart"].loc["5 期", "全樣本 Holm 候選"], 2)
        self.assertEqual(state["window_signal_chart"].loc["10 期", "全樣本 Holm 候選"], 1)
        self.assertEqual(state["window_signal_chart"]["留出驗證通過"].sum(), 0)
        self.assertEqual(state["holdout_flow_chart"]["探索期候選"].sum(), 10)
        self.assertEqual(state["holdout_flow_chart"]["通過留出驗證"].sum(), 0)
        self.assertIn("總頻率 Holm 顯著數", state["frequency_chart"].columns)

    def test_filtering_one_family_rebuilds_all_table_and_chart_views(self):
        state = build_long_window_research_state(
            PROJECT_ROOT / "data" / "long_window_research_snapshot.json"
        )
        filtered = filter_long_window_research(state, ["連號對"])

        self.assertEqual(filtered["total_tests"], 48)
        self.assertEqual(filtered["family_table"]["組合家族"].tolist(), ["連號對"])
        self.assertEqual(len(filtered["holdout_table"]), 2)
        self.assertEqual(filtered["initial_signals"], {"5": 1, "10": 0})
        self.assertEqual(filtered["window_signal_chart"].loc["5 期", "全樣本 Holm 候選"], 1)
        self.assertEqual(filtered["holdout_flow_chart"]["探索期候選"].sum(), 2)
        self.assertEqual(filtered["passed_holdout"], 0)

    def test_empty_family_filter_returns_empty_tables_and_zeroed_window_series(self):
        state = build_long_window_research_state(
            PROJECT_ROOT / "data" / "long_window_research_snapshot.json"
        )
        filtered = filter_long_window_research(state, [])

        self.assertTrue(filtered["family_table"].empty)
        self.assertTrue(filtered["holdout_table"].empty)
        self.assertEqual(filtered["total_tests"], 0)
        self.assertEqual(filtered["window_signal_chart"].to_numpy().sum(), 0)


if __name__ == "__main__":
    unittest.main()
