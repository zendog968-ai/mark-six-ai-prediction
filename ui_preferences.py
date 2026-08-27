"""Small local preference store for non-statistical dashboard display settings."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_UI_PREFERENCES_PATH = Path(__file__).resolve().parent / "data" / "dashboard_preferences.json"
WINDOW_RESEARCH_LANGUAGE_KEY = "window_research_language"
EMAIL_REPORT_THEME_KEY = "email_report_theme"
SUPPORTED_WINDOW_RESEARCH_LANGUAGES = {"zh", "en"}


def load_dashboard_preferences(path: Path | None = None) -> dict[str, Any]:
    """Return the local display-preference mapping, or an empty mapping when absent/invalid."""
    path = path or DEFAULT_UI_PREFERENCES_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_window_research_language(path: Path | None = None) -> str:
    """Read the persisted language; Traditional Chinese remains the safe default."""
    language = load_dashboard_preferences(path).get(WINDOW_RESEARCH_LANGUAGE_KEY)
    return language if language in SUPPORTED_WINDOW_RESEARCH_LANGUAGES else "zh"


def save_window_research_language(language: str, path: Path | None = None) -> None:
    """Atomically save a supported local display preference without touching research data."""
    if language not in SUPPORTED_WINDOW_RESEARCH_LANGUAGES:
        raise ValueError(f"Unsupported window-research language: {language!r}")
    path = path or DEFAULT_UI_PREFERENCES_PATH
    preferences = load_dashboard_preferences(path)
    preferences[WINDOW_RESEARCH_LANGUAGE_KEY] = language
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        json.dump(preferences, temporary, ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, path)


def load_email_report_theme(path: Path | None = None) -> str:
    """Read a display-only Email theme without touching prediction or audit data."""
    from report_themes import normalise_email_report_theme

    return normalise_email_report_theme(load_dashboard_preferences(path).get(EMAIL_REPORT_THEME_KEY))


def save_email_report_theme(theme: str, path: Path | None = None) -> None:
    """Atomically persist a supported Email display theme in the local UI preferences."""
    from report_themes import EMAIL_REPORT_THEME_OPTIONS

    if theme not in EMAIL_REPORT_THEME_OPTIONS:
        raise ValueError(f"Unsupported email report theme: {theme!r}")
    path = path or DEFAULT_UI_PREFERENCES_PATH
    preferences = load_dashboard_preferences(path)
    preferences[EMAIL_REPORT_THEME_KEY] = theme
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        json.dump(preferences, temporary, ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.chmod(temporary_path, 0o600)
    os.replace(temporary_path, path)


def language_code_from_label(label: str) -> str:
    """Convert the UI option label to the canonical stored language code."""
    return "en" if label == "English" else "zh"


def language_label_from_code(language: str) -> str:
    """Convert a stored language code to the corresponding UI option label."""
    return "English" if language == "en" else "繁體中文"
