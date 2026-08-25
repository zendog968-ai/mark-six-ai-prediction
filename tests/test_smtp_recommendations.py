import json
import tempfile
import unittest
from pathlib import Path

from smtp_notifications import build_email_message, render_daily_status_body, render_daily_status_html, render_prediction_verification_body


def six_plus_one_recommendation() -> dict:
    return {
        "set_index": 1,
        "numbers": [12, 23, 28, 34, 41, 45],
        "special_number": 8,
        "recommendation_format": "6+1",
    }


class SmtpRecommendationFormatTests(unittest.TestCase):
    def sample_snapshot(self) -> dict:
        return {
            "generated_at_hkt": "2026-08-25T22:00:00+08:00",
            "latest_official_draw": {"draw": 26092, "date": "2026-08-22", "numbers": [7, 9, 12, 25, 34, 40]},
            "latest_blind": {},
            "latest_brier": {},
            "weight_version": {},
            "latest_prediction": {"top_5_recommendations": [six_plus_one_recommendation(), {"set_index": 2, "numbers": [1, 2, 3, 4, 5, 6], "recommendation_format": "6"}]},
            "common_brier_draws": 0,
            "formal_gate": "等待",
        }

    def test_daily_status_renders_first_recommendation_as_six_plus_one(self):
        body = render_daily_status_body(self.sample_snapshot())
        self.assertIn("二、最新模型研究組合", body)
        self.assertIn("6+1 推薦組合：12、23、28、34、41、45 + [特別號碼：08]", body)
        self.assertIn("組合 2：01、02、03、04、05、06", body)

    def test_daily_status_html_emphasizes_special_number_and_keeps_plain_fallback(self):
        snapshot = self.sample_snapshot()
        plain_body = render_daily_status_body(snapshot)
        html_body = render_daily_status_html(snapshot)
        self.assertIn("6+1 推薦組合", html_body)
        self.assertIn("<strong>特別號碼：08</strong>", html_body)
        self.assertIn("background:#fef3c7", html_body)
        self.assertIn("border:1px solid #f59e0b", html_body)
        self.assertIn("組合 2", html_body)
        message = build_email_message(
            {"sender": "sender@example.test", "recipient": "recipient@example.test"},
            "daily summary",
            plain_body,
            html_body=html_body,
        )
        self.assertTrue(message.is_multipart())
        parts = message.get_payload()
        self.assertEqual(parts[0].get_content_type(), "text/plain")
        self.assertEqual(parts[1].get_content_type(), "text/html")
        self.assertIn("6+1 推薦組合", parts[0].get_content())
        self.assertIn("<strong>特別號碼：08</strong>", parts[1].get_content())

    def test_prediction_verification_renders_first_recommendation_as_six_plus_one(self):
        report = {
            "target_draw": 26093,
            "latest_verified_draw": {"draw": 26092},
            "history_records": 226,
            "top_weights_match_locked": True,
            "recommendations_match_locked": True,
            "rebuilt_top_weights": [],
            "rebuilt_recommendations": [six_plus_one_recommendation()],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "runtime_prediction_verification.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            _subject, body = render_prediction_verification_body(path)
        self.assertIn("6+1 推薦組合：12、23、28、34、41、45 + [特別號碼：08]", body)


if __name__ == "__main__":
    unittest.main()
