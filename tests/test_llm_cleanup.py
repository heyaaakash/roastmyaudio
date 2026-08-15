"""Tests for src/shared/llm_cleanup.py (Embedded Metal LLM Engine)"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared.llm_cleanup import (  # noqa: E402
    build_prompt,
    clean,
    format_chatml_prompt,
    get_tone,
)


class TestGetTone:
    def test_mail_app(self):
        assert "email" in get_tone("Mail").lower()

    def test_slack_app(self):
        assert "casual" in get_tone("Slack").lower()

    def test_unknown_app_defaults(self):
        tone = get_tone("MyRandomApp123")
        assert tone  # Should return default tone

    def test_empty_app_defaults(self):
        assert get_tone("") == get_tone(None)


class TestBuildPrompt:
    def test_includes_raw_text(self):
        prompt = build_prompt("um hello world", "mail")
        assert "hello world" in prompt

    def test_output_only_instruction_present(self):
        prompt = build_prompt("test", None)
        assert "OUTPUT ONLY" in prompt

    def test_chatml_formatting(self):
        chatml = format_chatml_prompt("um hello world", "slack")
        assert "<|im_start|>system" in chatml
        assert "um hello world" in chatml
        assert "<|im_start|>assistant\n" in chatml


class TestClean:
    def test_empty_input_passthrough(self):
        result, ms = clean("", None)
        assert result == ""
        assert ms == 0

    def test_whitespace_only_passthrough(self):
        result, ms = clean("   ", None)
        assert result.strip() == ""

    def test_short_utterance_passthrough(self):
        # 1-2 words bypass LLM for 0ms latency
        result, ms = clean("hello there", None)
        assert result == "hello there"
        assert ms == 0

    def test_model_unavailable_returns_raw(self):
        with patch("src.shared.llm_cleanup.get_llm", return_value=None):
            result, ms = clean("um hello world this is a test", None)
        assert result == "um hello world this is a test"
        assert ms == 0

    def test_successful_clean(self):
        mock_llm = MagicMock()
        mock_llm.return_value = {
            "choices": [{"text": "Hello world, this is a test."}]
        }
        with patch("src.shared.llm_cleanup.get_llm", return_value=mock_llm):
            result, ms = clean("um hello world uh this is a test", None)
        assert result == "Hello world, this is a test."
        assert ms >= 0

    def test_rewrite_detection_falls_back(self):
        """If model hallucinates a completely different rewrite, return raw text."""
        mock_llm = MagicMock()
        mock_llm.return_value = {
            "choices": [{"text": "The quick brown fox jumped over the lazy dogs today in Paris."}]
        }
        with patch("src.shared.llm_cleanup.get_llm", return_value=mock_llm):
            raw = "please buy some fresh organic milk from the store tomorrow"
            result, _ = clean(raw, None)
        assert result == raw

    def test_refusal_returns_raw(self):
        mock_llm = MagicMock()
        mock_llm.return_value = {
            "choices": [{"text": "I cannot fulfill this request as an AI."}]
        }
        with patch("src.shared.llm_cleanup.get_llm", return_value=mock_llm):
            result, _ = clean("some voice text here to test", None)
        assert result == "some voice text here to test"

    def test_preamble_stripped(self):
        mock_llm = MagicMock()
        mock_llm.return_value = {
            "choices": [{"text": "Here is the cleaned text: Hello world this is a test."}]
        }
        with patch("src.shared.llm_cleanup.get_llm", return_value=mock_llm):
            result, _ = clean("um hello world uh this is a test", None)
        assert not result.lower().startswith("here is")
        assert "Hello world this is a test." in result

    def test_model_exception_returns_raw(self):
        mock_llm = MagicMock()
        mock_llm.side_effect = RuntimeError("GPU out of memory")
        with patch("src.shared.llm_cleanup.get_llm", return_value=mock_llm):
            result, _ = clean("um hello world uh this is a test", None)
        assert result == "um hello world uh this is a test"
