"""Tests for src/shared/context_detector.py"""

import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared.context_detector import (  # noqa: E402
    MODE_CHAT,
    MODE_CODE,
    MODE_EMAIL_DOC,
    MODE_GENERAL,
    build_whisper_prompt,
    extract_clipboard_keywords,
    get_app_mode,
    get_llm_mode_guidance,
)


class TestGetAppMode:
    def test_code_apps(self):
        assert get_app_mode("Visual Studio Code") == MODE_CODE
        assert get_app_mode("Cursor") == MODE_CODE
        assert get_app_mode("Xcode") == MODE_CODE
        assert get_app_mode("iTerm2") == MODE_CODE
        assert get_app_mode("Ghostty") == MODE_CODE
        assert get_app_mode("PyCharm CE") == MODE_CODE

    def test_chat_apps(self):
        assert get_app_mode("Slack") == MODE_CHAT
        assert get_app_mode("Discord") == MODE_CHAT
        assert get_app_mode("Messages") == MODE_CHAT
        assert get_app_mode("Telegram") == MODE_CHAT
        assert get_app_mode("WhatsApp") == MODE_CHAT

    def test_email_doc_apps(self):
        assert get_app_mode("Mail") == MODE_EMAIL_DOC
        assert get_app_mode("Microsoft Outlook") == MODE_EMAIL_DOC
        assert get_app_mode("Notion") == MODE_EMAIL_DOC
        assert get_app_mode("Obsidian") == MODE_EMAIL_DOC
        assert get_app_mode("Linear") == MODE_EMAIL_DOC

    def test_general_fallback(self):
        assert get_app_mode("Safari") == MODE_GENERAL
        assert get_app_mode("Google Chrome") == MODE_GENERAL
        assert get_app_mode("") == MODE_GENERAL
        assert get_app_mode(None) == MODE_GENERAL


class TestExtractClipboardKeywords:
    def test_empty_or_none(self):
        assert extract_clipboard_keywords("") == []
        assert extract_clipboard_keywords(None) == []

    def test_extracts_camel_case_and_snake_case(self):
        text = "def get_user_profile(userId, PodDisruptionBudget, API_KEY_SECRET): pass"
        tokens = extract_clipboard_keywords(text)
        assert "get_user_profile" in tokens
        assert "userId" in tokens
        assert "PodDisruptionBudget" in tokens
        assert "API_KEY_SECRET" in tokens

    def test_extracts_dot_notation(self):
        text = "import os.path.exists and sys.version_info"
        tokens = extract_clipboard_keywords(text)
        assert any("os.path" in t for t in tokens)

    def test_caps_max_tokens(self):
        text = "oneTwo threeFour fiveSix sevenEight nineTen elevenTwelve thirteenFourteen fifteenSixteen"
        tokens = extract_clipboard_keywords(text, max_tokens=3)
        assert len(tokens) <= 3


class TestBuildWhisperPrompt:
    def test_includes_custom_words(self):
        prompt = build_whisper_prompt(
            app_name="Cursor",
            clipboard_text="const apiSecretKey = '123';",
            custom_words=["Kubernetes", "MyCustomModule"],
        )
        assert "Kubernetes" in prompt
        assert "MyCustomModule" in prompt
        assert "apiSecretKey" in prompt

    def test_code_mode_includes_code_vocab(self):
        prompt = build_whisper_prompt(app_name="VS Code")
        assert "API" in prompt or "JSON" in prompt or "async" in prompt

    def test_chat_mode_includes_chat_vocab(self):
        prompt = build_whisper_prompt(app_name="Slack")
        assert "LGTM" in prompt or "thanks" in prompt or "sync" in prompt


class TestGetLLMModeGuidance:
    def test_code_mode_guidance(self):
        guidance = get_llm_mode_guidance("Cursor")
        assert "Code Editor" in guidance

    def test_chat_mode_guidance(self):
        guidance = get_llm_mode_guidance("Slack")
        assert "Chat" in guidance

    def test_email_mode_guidance(self):
        guidance = get_llm_mode_guidance("Mail")
        assert "Email" in guidance
