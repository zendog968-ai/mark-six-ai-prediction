from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from daily_report_archive import (
    append_reconstructed_daily_report,
    daily_report_archive_index,
    load_daily_report_archive,
    mark_daily_report_sent,
    prepare_daily_report_archive,
    search_daily_report_archive,
)
from smtp_notifications import dispatch_daily_status
from scripts.backfill_daily_report_archive import event_timestamp_hkt


def _snapshot() -> dict:
    return {
        "report_date_hkt": "2026-08-25",
        "generated_at_hkt": "2026-08-25T22:00:00+08:00",
        "latest_official_draw": {"draw": "26092", "date": "2026-08-22", "numbers": [7, 9, 12, 25, 34, 40]},
        "latest_blind": {},
        "latest_brier": {},
        "weight_version": {},
        "latest_prediction": {
            "top_5_recommendations": [
                {"set_index": 1, "numbers": [1, 3, 7, 11, 23, 48], "special_number": 13, "relative_strength_percent": 100}
            ]
        },
        "recent_blind_hit_summary": {"settled_draws": 2, "average_best_hits": 1.0, "recent": [], "note": "只統計已結算盲測。"},
        "common_brier_draws": 0,
        "formal_gate": "等待 100 期",
    }


class DailyReportArchiveTests(unittest.TestCase):
    def test_historical_event_timestamp_converts_to_hong_kong_date(self) -> None:
        report_date, display_time = event_timestamp_hkt("2026-08-22T17:21:42+00:00")
        self.assertEqual(report_date, "2026-08-23")
        self.assertTrue(display_time.endswith("+08:00"))

    def test_prepare_deduplicates_and_marks_sent_without_rewriting_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily_report_archive.json"
            original_snapshot = _snapshot()
            report, created = prepare_daily_report_archive("daily-20260825", original_snapshot, "plain 26092", "<p>html 26092</p>", path=path)
            self.assertTrue(created)
            reused, created_again = prepare_daily_report_archive("daily-20260825", {"report_date_hkt": "changed"}, "changed", "<p>changed</p>", path=path)
            self.assertFalse(created_again)
            self.assertEqual(reused["plain_body"], "plain 26092")
            self.assertTrue(mark_daily_report_sent("daily-20260825", path=path))
            saved = load_daily_report_archive(path)
            self.assertEqual(saved[0]["delivery_status"], "sent")
            self.assertEqual(saved[0]["snapshot"], original_snapshot)

    def test_search_and_index_only_expose_sent_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily_report_archive.json"
            prepare_daily_report_archive("pending", _snapshot(), "plain pending", "<p>pending</p>", path=path)
            sent_snapshot = _snapshot()
            sent_snapshot["latest_official_draw"]["draw"] = "26091"
            prepare_daily_report_archive("sent", sent_snapshot, "6+1 推薦組合 26091", "<p>6+1</p>", path=path)
            mark_daily_report_sent("sent", path=path)
            records = load_daily_report_archive(path)
            found = search_daily_report_archive(records, query="6+1", latest_draw="26091")
            self.assertEqual([record["archive_id"] for record in found], ["sent"])
            index = daily_report_archive_index(found)
            self.assertEqual(index[0]["最新官方期數"], "26091")
            self.assertEqual(index[0]["第一組相對強度"], "100%")

    def test_reconstructed_sent_report_is_searchable_and_labelled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily_report_archive.json"
            append_reconstructed_daily_report(
                "legacy-sent",
                _snapshot(),
                "legacy 6+1 report",
                "<p>legacy</p>",
                source_revision="a028343",
                source_event_sent_at_utc="2026-08-22T17:21:42+00:00",
                path=path,
            )
            found = search_daily_report_archive(load_daily_report_archive(path), query="legacy")
            self.assertEqual(found[0]["delivery_status"], "sent_reconstructed")
            self.assertIn("Git", found[0]["content_provenance"])
            self.assertEqual(daily_report_archive_index(found)[0]["內容來源"], "歷史可追溯重建")

    def test_reconstructed_report_can_refresh_derived_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily_report_archive.json"
            append_reconstructed_daily_report(
                "legacy-refresh", _snapshot(), "old", "<p>old</p>", source_revision="old", source_event_sent_at_utc="2026-08-22T17:00:00+00:00", path=path
            )
            refreshed_snapshot = _snapshot()
            refreshed_snapshot["report_date_hkt"] = "2026-08-23"
            refreshed, changed = append_reconstructed_daily_report(
                "legacy-refresh", refreshed_snapshot, "new", "<p>new</p>", source_revision="new", source_event_sent_at_utc="2026-08-22T17:00:00+00:00", refresh_reconstruction=True, path=path
            )
            self.assertTrue(changed)
            self.assertEqual(refreshed["report_date_hkt"], "2026-08-23")
            self.assertEqual(refreshed["source_revision"], "new")
            self.assertIn("reconstructed_at_utc", refreshed)

            unchanged, changed_again = append_reconstructed_daily_report(
                "legacy-refresh", refreshed_snapshot, "new", "<p>new</p>", source_revision="new", source_event_sent_at_utc="2026-08-22T17:00:00+00:00", refresh_reconstruction=True, path=path
            )
            self.assertFalse(changed_again)
            self.assertEqual(unchanged["prepared_at_utc"], refreshed["prepared_at_utc"])

    def test_dispatch_archives_only_after_successful_submission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "daily_report_archive.json"
            ledger_path = root / "daily_ledger.json"
            sent: list[tuple[str, str]] = []

            def send_stub(_settings: dict, subject: str, body: str) -> None:
                sent.append((subject, body))

            result = dispatch_daily_status(
                {"sender": "a", "recipient": "b", "host": "x", "port": 465, "username": "a", "password": "p"},
                ledger_path=ledger_path,
                archive_path=archive_path,
                snapshot=_snapshot(),
                send_func=send_stub,
            )
            self.assertEqual(result["sent"], 1)
            self.assertEqual(len(sent), 1)
            saved = load_daily_report_archive(archive_path)
            self.assertEqual(saved[0]["delivery_status"], "sent")
            self.assertIn("6+1", saved[0]["plain_body"])
