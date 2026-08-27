import json
import tempfile
import unittest
from pathlib import Path

from ui_preferences import (
    load_email_report_theme,
    language_code_from_label,
    language_label_from_code,
    save_email_report_theme,
    load_window_research_language,
    save_window_research_language,
)


class UiPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.preference_path = Path(self.temporary_directory.name) / "preferences.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_language_defaults_to_traditional_chinese_when_missing_or_invalid(self):
        self.assertEqual(load_window_research_language(self.preference_path), "zh")
        self.preference_path.write_text("{not valid json", encoding="utf-8")
        self.assertEqual(load_window_research_language(self.preference_path), "zh")

    def test_language_round_trip_persists_and_preserves_other_preference_keys(self):
        self.preference_path.write_text(json.dumps({"other_setting": True}), encoding="utf-8")
        save_window_research_language("en", self.preference_path)
        self.assertEqual(load_window_research_language(self.preference_path), "en")
        payload = json.loads(self.preference_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["other_setting"])
        self.assertEqual(payload["window_research_language"], "en")

    def test_language_helpers_convert_labels_without_accepting_unknown_values(self):
        self.assertEqual(language_code_from_label("English"), "en")
        self.assertEqual(language_code_from_label("繁體中文"), "zh")
        self.assertEqual(language_label_from_code("en"), "English")
        self.assertEqual(language_label_from_code("invalid"), "繁體中文")
        with self.assertRaises(ValueError):
            save_window_research_language("invalid", self.preference_path)

    def test_email_theme_round_trip_preserves_language_and_rejects_unknown_theme(self):
        save_window_research_language("en", self.preference_path)
        self.assertEqual(load_email_report_theme(self.preference_path), "standard")
        save_email_report_theme("dark", self.preference_path)
        self.assertEqual(load_email_report_theme(self.preference_path), "dark")
        payload = json.loads(self.preference_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["window_research_language"], "en")
        self.assertEqual(payload["email_report_theme"], "dark")
        with self.assertRaises(ValueError):
            save_email_report_theme("invalid", self.preference_path)
