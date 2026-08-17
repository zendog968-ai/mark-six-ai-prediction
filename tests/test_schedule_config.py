import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ScheduleConfigurationTests(unittest.TestCase):
    def test_workflow_uses_hong_kong_2230_as_utc_1430_and_commits_generated_files(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "schedule.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "30 14 * * 2,4,6"', content)
        self.assertIn("python updater.py", content)
        self.assertIn("data/lotto_history_real.csv", content)
        self.assertIn("data/latest_prediction.json", content)
        self.assertIn("contents: write", content)


if __name__ == "__main__":
    unittest.main()
