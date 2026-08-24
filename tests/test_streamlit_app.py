import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class StreamlitApplicationTests(unittest.TestCase):
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
        self.assertIn("總頻率 Holm 狀態", source)
        self.assertIn("窗口 Holm 狀態", source)


if __name__ == "__main__":
    unittest.main()
