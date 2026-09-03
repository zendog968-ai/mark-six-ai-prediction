import tempfile
import unittest
from pathlib import Path

from schedule_health import (
    begin_schedule_run,
    finish_schedule_run,
    load_schedule_health,
    record_data_change,
    record_schedule_step,
    schedule_health_index,
)


class ScheduleHealthTests(unittest.TestCase):
    def test_run_records_steps_data_change_and_completion_without_sensitive_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "schedule_health_summary.json"
            first, created = begin_schedule_run(
                "cron-20260827-2200",
                "2026-08-27T22:00:00+08:00",
                path=path,
                started_at_utc="2026-08-27T14:00:01+00:00",
                started_at_hkt="2026-08-27T22:00:01+08:00",
            )
            duplicate, created_again = begin_schedule_run("cron-20260827-2200", "changed", path=path)
            record_schedule_step(
                "cron-20260827-2200",
                "updater",
                "completed",
                exit_code=0,
                duration_seconds=8,
                detail="public update completed",
                path=path,
                recorded_at_utc="2026-08-27T14:00:09+00:00",
            )
            record_data_change("cron-20260827-2200", False, path=path)
            finished = finish_schedule_run(
                "cron-20260827-2200",
                "completed",
                detail="daily scheduled pipeline completed",
                path=path,
                completed_at_utc="2026-08-27T14:00:13+00:00",
                completed_at_hkt="2026-08-27T22:00:13+08:00",
            )
            loaded = load_schedule_health(path)
            rows = schedule_health_index(loaded)
            rendered = path.read_text(encoding="utf-8").lower()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["run_id"], duplicate["run_id"])
        self.assertEqual(finished["status"], "completed")
        self.assertFalse(loaded["latest"]["data_changed"])
        self.assertEqual(loaded["latest"]["steps"][0]["exit_code"], 0)
        self.assertEqual(rows[0]["整體狀態"], "completed")
        self.assertEqual(rows[0]["資料結果"], "未變更")
        self.assertNotIn("password", rendered)

    def test_failed_step_and_degraded_completion_are_displayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "schedule_health_summary.json"
            begin_schedule_run("cron-failure", "2026-08-28T22:00:00+08:00", path=path)
            record_schedule_step(
                "cron-failure", "daily_summary", "failed", exit_code=1, duration_seconds=2, detail="smtp dispatch failed", path=path
            )
            finish_schedule_run("cron-failure", "degraded", detail="notification step failed", path=path)
            row = schedule_health_index(load_schedule_health(path))[0]
        self.assertEqual(row["整體狀態"], "degraded")
        self.assertIn("daily_summary：failed", row["步驟摘要"])

    def test_unknown_run_and_unsupported_status_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "schedule_health_summary.json"
            with self.assertRaisesRegex(ValueError, "找不到排程執行紀錄"):
                record_data_change("absent", True, path=path)
            begin_schedule_run("cron-invalid", "2026-08-28T22:00:00+08:00", path=path)
            with self.assertRaisesRegex(ValueError, "不支援的排程步驟狀態"):
                record_schedule_step("cron-invalid", "updater", "unknown", exit_code=0, duration_seconds=0, path=path)
