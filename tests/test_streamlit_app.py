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
        self.assertIn("模擬資料", rendered_info)


if __name__ == "__main__":
    unittest.main()
