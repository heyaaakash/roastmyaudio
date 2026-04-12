"""Tests for src/shared/llm_cleanup.py"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared.llm_cleanup import build_prompt, clean, get_tone  # noqa: E402


class TestGetTone:
    def test_mail_app(self):
        assert "email" in get_tone("Mail").lower()

    def test_slack_app(self):
        assert "casual" in get_tone("Slack").lower()

    def test_unknown_app_defaults(self):
        tone = get_tone("MyRandomApp123")
        assert tone  # Should return something, not empty

    def test_empty_app_defaults(self):
        assert get_tone("") == get_tone("unknown")


class TestBuildPrompt:
    def test_includes_raw_text(self):
        prompt = build_prompt("um hello world", "mail")
        assert "hello world" in prompt

    def test_output_only_instruction_present(self):
        prompt = build_prompt("test", None)
        assert "OUTPUT ONLY" in prompt


class TestClean:
    def test_empty_input_passthrough(self):
        result, ms = clean("", None)
        assert result == ""
        assert ms == 0

    def test_whitespace_only_passthrough(self):
        result, ms = clean("   ", None)
        assert result.strip() == ""

    def test_connection_error_returns_raw(self):
        import requests
        with patch("src.shared.llm_cleanup.requests.post", side_effect=requests.exceptions.ConnectionError):
            result, ms = clean("hello world", None)
        assert result == "hello world"
        assert ms == 0

    def test_timeout_returns_raw(self):
        import requests
        with patch("src.shared.llm_cleanup.requests.post", side_effect=requests.exceptions.Timeout):
            result, ms = clean("hello world", None)
        assert result == "hello world"

    def test_successful_clean(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Hello world."}
        mock_resp.raise_for_status.return_value = None
        with patch("src.shared.llm_cleanup.requests.post", return_value=mock_resp):
            result, ms = clean("um hello world uh", None)
        assert result == "Hello world."
        assert ms >= 0

    def test_rewrite_detection_falls_back(self):
        """If model rewrites >30% of words, return raw text."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": "The quick brown fox jumped over the lazy dogs today."
        }
        mock_resp.raise_for_status.return_value = None
        with patch("src.shared.llm_cleanup.requests.post", return_value=mock_resp):
            raw = "please buy milk from the store tomorrow"
            result, _ = clean(raw, None)
        # Should fall back to original because word overlap is < 70%
        assert result == raw

    def test_refusal_returns_raw(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "I cannot process this request."}
        mock_resp.raise_for_status.return_value = None
        with patch("src.shared.llm_cleanup.requests.post", return_value=mock_resp):
            result, _ = clean("some text", None)
        assert result == "some text"

    def test_preamble_stripped(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Here is the cleaned text: Hello world."}
        mock_resp.raise_for_status.return_value = None
        with patch("src.shared.llm_cleanup.requests.post", return_value=mock_resp):
            result, _ = clean("um hello world uh", None)
        assert not result.lower().startswith("here is")
