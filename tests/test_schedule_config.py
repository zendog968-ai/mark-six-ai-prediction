import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ScheduleConfigurationTests(unittest.TestCase):
    def test_workflow_runs_daily_at_hong_kong_2200_and_commits_generated_files(self):
        content = (PROJECT_ROOT / ".github" / "workflows" / "schedule.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "0 14 * * *"', content)
        self.assertIn("every day", content)
        self.assertIn("python updater.py", content)
        self.assertIn("data/lotto_history_real.csv", content)
        self.assertIn("data/latest_prediction.json", content)
        self.assertIn("data/prediction_history.json", content)
        self.assertIn("contents: write", content)
        self.assertIn("Verify public Streamlit deployment", content)
        self.assertIn("STREAMLIT_HEALTH_URL", content)
        self.assertIn("/healthz", content)
        self.assertIn("for attempt in 1 2 3", content)


if __name__ == "__main__":
    unittest.main()
