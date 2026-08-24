import unittest
from pathlib import Path

from long_window_research import build_long_window_research_state


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


if __name__ == "__main__":
    unittest.main()
