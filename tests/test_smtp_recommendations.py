import json
import tempfile
import unittest
from pathlib import Path

from smtp_notifications import build_email_message, build_recent_blind_hit_summary, render_daily_status_body, render_daily_status_html, render_prediction_verification_body


def six_plus_one_recommendation() -> dict:
    return {
        "set_index": 1,
        "numbers": [12, 23, 28, 34, 41, 45],
        "special_number": 8,
        "recommendation_format": "6+1",
        "relative_strength_percent": 100,
        "strength_label": "相對推薦強度 100%",
    }


class SmtpRecommendationFormatTests(unittest.TestCase):
    def sample_snapshot(self) -> dict:
        return {
            "generated_at_hkt": "2026-08-25T22:00:00+08:00",
            "latest_official_draw": {"draw": 26092, "date": "2026-08-22", "numbers": [7, 9, 12, 25, 34, 40]},
            "latest_blind": {},
            "latest_brier": {},
            "weight_version": {},
            "latest_prediction": {
                "top_5_recommendations": [six_plus_one_recommendation(), {"set_index": 2, "numbers": [1, 2, 3, 4, 5, 6], "recommendation_format": "6", "relative_strength_percent": 88, "strength_label": "相對推薦強度 88%"}],
                "colour_analysis": {
                    "latest_official_draw": {"draw": 26092, "main_colour_composition": "紅色 3、藍色 2、綠色 1", "special_colour": "紅色"},
                    "recent_windows": [
                        {"範圍": "最近 10 期", "球色": "紅色", "正選實際球數": 22},
                        {"範圍": "最近 10 期", "球色": "藍色", "正選實際球數": 19},
                        {"範圍": "最近 10 期", "球色": "綠色", "正選實際球數": 19},
                    ],
                },
            },
            "recent_blind_hit_summary": {"settled_draws": 1, "average_best_hits": 2.0, "recent": [{"target_draw": 26092, "best_hits": 2, "average_hits": 1.0, "best_labels": ["融合模型 Top-6"]}], "note": "只統計已鎖定紀錄。"},
            "common_brier_draws": 0,
            "formal_gate": "等待",
        }

    def test_daily_status_renders_first_recommendation_as_six_plus_one(self):
        body = render_daily_status_body(self.sample_snapshot())
        self.assertIn("二、號碼球顏色研究摘要", body)
        self.assertIn("三、最新模型研究組合", body)
        self.assertIn("6+1 推薦組合：12、23、28、34、41、45 + [特別號碼：08／紅色]", body)
        self.assertIn("最近 10 期 正選球色總數：紅色 22、藍色 19、綠色 19", body)
        self.assertIn("組合 2：01、02、03、04、05、06", body)

    def test_daily_status_html_emphasizes_special_number_and_keeps_plain_fallback(self):
        snapshot = self.sample_snapshot()
        plain_body = render_daily_status_body(snapshot)
        html_body = render_daily_status_html(snapshot)
        self.assertIn("6+1 推薦組合", html_body)
        self.assertIn("<strong>特別號碼：08／紅色</strong>", html_body)
        self.assertIn("background:#dc2626", html_body)
        self.assertIn("border:2px solid #f59e0b", html_body)
        self.assertIn("box-shadow:0 0 0 1px #ffffff", html_body)
        self.assertIn("background:#dc2626", html_body)
        self.assertIn("background:#16a34a", html_body)
        self.assertIn("球色組成：", html_body)
        self.assertIn("二、號碼球顏色研究摘要", html_body)
        self.assertIn("相對推薦強度 100%", html_body)
        self.assertIn("近期盲測命中摘要", html_body)
        self.assertIn("26092：最高 2/6", plain_body)
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
        self.assertIn("<strong>特別號碼：08／紅色</strong>", parts[1].get_content())

    def test_recent_blind_summary_uses_only_draws_with_official_main_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            draw_path = Path(temporary) / "draws.csv"
            draw_path.write_text(
                "Draw,Date,N1,N2,N3,N4,N5,N6,Special\n26092,2026-08-22,7,9,12,25,34,40,29\n",
                encoding="utf-8",
            )
            records = [
                {"target_draw": 26092, "target_date": "2026-08-22", "variants": [{"label": "基準", "numbers": [7, 9, 1, 2, 3, 4]}, {"label": "熱門", "numbers": [12, 25, 30, 31, 32, 33]}]},
                {"target_draw": 26093, "target_date": "2026-08-25", "variants": [{"label": "待攪珠", "numbers": [1, 2, 3, 4, 5, 6]}]},
            ]
            summary = build_recent_blind_hit_summary(records, draw_history_path=draw_path)
        self.assertEqual(summary["settled_draws"], 1)
        self.assertEqual(summary["recent"][0]["target_draw"], 26092)
        self.assertEqual(summary["recent"][0]["best_hits"], 2)

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
        self.assertIn("6+1 推薦組合：12、23、28、34、41、45 + [特別號碼：08／紅色]", body)


if __name__ == "__main__":
    unittest.main()
