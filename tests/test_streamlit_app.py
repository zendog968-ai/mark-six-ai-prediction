import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import ui_preferences


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StreamlitApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.preference_path = Path(self.temporary_directory.name) / "dashboard_preferences.json"
        self.preference_patch = patch.object(ui_preferences, "DEFAULT_UI_PREFERENCES_PATH", self.preference_path)
        self.preference_patch.start()

    def tearDown(self):
        self.preference_patch.stop()
        self.temporary_directory.cleanup()

    def test_sidebar_exposes_csv_uploader_and_renders_the_default_source(self):
        app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30)
        app.run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.sidebar.file_uploader), 1)
        rendered_info = " ".join(info.value for info in app.info)
        self.assertIn("目前資料來源：", rendered_info)
        self.assertIn("專案真實歷史 CSV", rendered_info)
        rendered_subheaders = " ".join(item.value for item in app.subheader)
        self.assertIn("命中率與回測分析", rendered_subheaders)
        rendered_captions = " ".join(item.value for item in app.caption)
        self.assertIn("游標移到長條", rendered_captions)
        self.assertIn("提示同時顯示實際聚集分數", rendered_captions)
        source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("st.altair_chart(frequency_chart", source)
        self.assertIn("st.altair_chart(window_trend_chart", source)
        self.assertIn("duration=\"long\"", source)
        self.assertIn("總頻率 Holm 狀態", source)
        self.assertIn("窗口 Holm 狀態", source)
        self.assertIn("HTML 每日報告預覽", source)
        self.assertIn("st.iframe(render_daily_status_html(report_snapshot, theme=preview_theme, preview_mode=True)", source)
        self.assertIn("Email 及預覽主題", source)
        self.assertIn("列印友善版面（強制白底）", source)
        self.assertIn("preview_mode=True", source)
        self.assertIn("歷史報告歸檔", source)
        self.assertIn("search_daily_report_archive", source)
        self.assertIn("選擇要預覽的歸檔報告", source)
        self.assertIn("每日排程健康摘要", source)
        self.assertIn("load_schedule_health", source)
        self.assertIn("最近 31 次排程摘要", source)
        self.assertIn("號碼球顏色分析", source)
        self.assertIn("固定球色對照來源", source)
        self.assertIn("顏色是號碼既定標籤", source)
        language_selectors = [widget for widget in app.selectbox if widget.label == "Language / 語言"]
        self.assertEqual(len(language_selectors), 1)
        language_selector = language_selectors[0]
        self.assertEqual(len(app.toast), 0)

        language_selector.set_value("English").run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.toast), 1)
        self.assertIn("Language preference saved: English", app.toast[0].value)
        english_subheaders = " ".join(item.value for item in app.subheader)
        english_captions = " ".join(item.value for item in app.caption)
        self.assertIn("5/10-draw window frequency research", english_subheaders)
        self.assertIn("Hover over a bar", english_captions)
        self.assertIn("Combination family", source)
        self.assertIn("Random expected score", source)
        self.assertEqual(ui_preferences.load_window_research_language(self.preference_path), "en")

        reopened = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30)
        reopened.run(timeout=30)
        self.assertFalse(reopened.exception)
        reopened_language = next(widget for widget in reopened.selectbox if widget.label == "Language / 語言")
        self.assertEqual(reopened_language.value, "English")
        self.assertEqual(len(reopened.toast), 0)

        reopened_language.set_value("繁體中文").run(timeout=30)
        self.assertFalse(reopened.exception)
        self.assertEqual(len(reopened.toast), 1)
        self.assertIn("已儲存語言偏好：繁體中文", reopened.toast[0].value)
        self.assertEqual(ui_preferences.load_window_research_language(self.preference_path), "zh")


if __name__ == "__main__":
    unittest.main()
