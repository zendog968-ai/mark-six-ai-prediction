"""Display-only theme definitions for the daily Mark Six HTML report."""

from __future__ import annotations

from typing import Any


DEFAULT_EMAIL_REPORT_THEME = "standard"

EMAIL_REPORT_THEME_OPTIONS: dict[str, dict[str, str]] = {
    "standard": {
        "label": "標準（淺色）",
        "page_background": "#f3f4f6",
        "shell_background": "#f9fafb",
        "card_background": "#ffffff",
        "border": "#e5e7eb",
        "heading": "#111827",
        "body_text": "#374151",
        "muted_text": "#6b7280",
        "header_background": "#111827",
        "header_text": "#ffffff",
        "header_muted": "#d1d5db",
        "strength_background": "#e0f2fe",
        "strength_text": "#075985",
        "strength_border": "#7dd3fc",
        "notice_background": "#eff6ff",
        "notice_text": "#1d4ed8",
        "notice_border": "#bfdbfe",
    },
    "high_contrast": {
        "label": "高對比",
        "page_background": "#ffffff",
        "shell_background": "#ffffff",
        "card_background": "#ffffff",
        "border": "#111111",
        "heading": "#000000",
        "body_text": "#000000",
        "muted_text": "#1f2937",
        "header_background": "#000000",
        "header_text": "#ffffff",
        "header_muted": "#ffffff",
        "strength_background": "#fff200",
        "strength_text": "#000000",
        "strength_border": "#000000",
        "notice_background": "#fff200",
        "notice_text": "#000000",
        "notice_border": "#000000",
    },
    "dark": {
        "label": "深色",
        "page_background": "#020617",
        "shell_background": "#0f172a",
        "card_background": "#111827",
        "border": "#475569",
        "heading": "#f8fafc",
        "body_text": "#e2e8f0",
        "muted_text": "#cbd5e1",
        "header_background": "#000000",
        "header_text": "#ffffff",
        "header_muted": "#cbd5e1",
        "strength_background": "#0c4a6e",
        "strength_text": "#e0f2fe",
        "strength_border": "#38bdf8",
        "notice_background": "#1e3a8a",
        "notice_text": "#dbeafe",
        "notice_border": "#60a5fa",
    },
}


def normalise_email_report_theme(theme: str | None) -> str:
    """Return a supported display theme; the safe default is the light report."""
    return theme if theme in EMAIL_REPORT_THEME_OPTIONS else DEFAULT_EMAIL_REPORT_THEME


def email_report_theme_label(theme: str | None) -> str:
    return EMAIL_REPORT_THEME_OPTIONS[normalise_email_report_theme(theme)]["label"]


def email_report_theme_code_from_label(label: str) -> str:
    for code, values in EMAIL_REPORT_THEME_OPTIONS.items():
        if values["label"] == label:
            return code
    return DEFAULT_EMAIL_REPORT_THEME


def email_report_theme_tokens(theme: str | None) -> dict[str, Any]:
    code = normalise_email_report_theme(theme)
    return {**EMAIL_REPORT_THEME_OPTIONS[code], "code": code}
