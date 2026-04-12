"""Tests for src/shared/formatter.py"""

import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared.formatter import (  # noqa: E402
    filter_hallucinations,
    format_transcript,
    format_transcript_strict,
)


# ---------------------------------------------------------------------------
# filter_hallucinations
# ---------------------------------------------------------------------------
class TestFilterHallucinations:
    def test_empty_string_passthrough(self):
        assert filter_hallucinations("") == ""

    def test_normal_text_unchanged(self):
        text = "Hello, this is a normal sentence."
        assert filter_hallucinations(text) == text

    def test_removes_dominant_repeated_word(self):
        # "you" appears 6/9 times — well over 10% threshold
        text = "you you you you you you the end"
        result = filter_hallucinations(text)
        assert "you" not in result.lower()

    def test_removes_high_filler_ratio(self):
        # >30% are filler words
        text = "um uh like the cat sat on the mat um uh"
        result = filter_hallucinations(text)
        # Result should be shorter / have less filler
        filler_count = sum(1 for w in result.lower().split() if w in {"um", "uh", "like"})
        assert filler_count < 3

    def test_short_text_passthrough(self):
        assert filter_hallucinations("hi") == "hi"


# ---------------------------------------------------------------------------
# format_transcript
# ---------------------------------------------------------------------------
class TestFormatTranscript:
    def test_empty_returns_empty(self):
        assert format_transcript("") == ""
        assert format_transcript("   ") == ""

    def test_capitalizes_first_letter(self):
        assert format_transcript("hello world").startswith("H")

    def test_adds_period_to_plain_sentence(self):
        result = format_transcript("the cat sat on the mat")
        assert result.endswith(".")

    def test_no_extra_period_if_already_punctuated(self):
        result = format_transcript("Are you sure?")
        assert result.count("?") == 1
        assert not result.endswith("?.")

    def test_spoken_new_line_command(self):
        result = format_transcript("first item new line second item")
        assert "\n" in result

    def test_spoken_period_command(self):
        result = format_transcript("Hello period World")
        assert "." in result

    def test_spoken_comma_command(self):
        result = format_transcript("one comma two comma three")
        assert "," in result

    def test_ordinal_step_list_two_items(self):
        result = format_transcript("first do the thing second do the other thing")
        assert "1." in result
        assert "2." in result

    def test_ordinal_single_item_no_list(self):
        # Only one ordinal — should NOT become a numbered list
        result = format_transcript("first of all make sure you save")
        assert "1." not in result

    def test_capitalization_after_period(self):
        result = format_transcript("Hello. world is round.")
        assert "World" in result


# ---------------------------------------------------------------------------
# format_transcript_strict
# ---------------------------------------------------------------------------
class TestFormatTranscriptStrict:
    def test_empty_returns_empty(self):
        assert format_transcript_strict("") == ""

    def test_normalizes_whitespace_only(self):
        result = format_transcript_strict("  hello   world  ")
        assert result == "hello world"

    def test_does_not_add_period(self):
        result = format_transcript_strict("hello world")
        assert not result.endswith(".")

    def test_does_not_capitalize(self):
        result = format_transcript_strict("hello world")
        assert result[0] == "h"
