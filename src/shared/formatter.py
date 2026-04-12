"""
Shared text formatting utilities for WhisperFlow.

Converts raw Whisper transcriptions into clean, human-readable text.
Handles spoken commands, punctuation, capitalization, and list formatting.
"""

import re

# ---------------------------------------------------------------------------
# Spoken command → text substitution table
# ---------------------------------------------------------------------------
SPOKEN_COMMAND_REPLACEMENTS = [
    (r"\bnew\s+paragraph\b", "\n\n"),
    (r"\b(new\s+line|next\s+line|line\s+break)\b", "\n"),
    (r"\b(bullet\s+point|bullet|dash\s+point)\b", "\n- "),
    (r"\bopen\s+parenthesis\b", "("),
    (r"\bclose\s+parenthesis\b", ")"),
    (r"\bopen\s+bracket\b", "("),
    (r"\bclose\s+bracket\b", ")"),
    (r"\bopen\s+quote\b", '"'),
    (r"\bclose\s+quote\b", '"'),
    (r"\bquote\s+unquote\b", '"'),
    (r"\b(comma)\b", ","),
    (r"\b(period|full\s+stop|dot)\b", "."),
    (r"\b(question\s+mark)\b", "?"),
    (r"\b(exclamation\s+mark|exclamation\s+point)\b", "!"),
    (r"\b(colon)\b", ":"),
    (r"\b(semicolon)\b", ";"),
]

COMPILED_SPOKEN_COMMAND_REPLACEMENTS = [
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in SPOKEN_COMMAND_REPLACEMENTS
]

ORDINAL_ORDER = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}

# ---------------------------------------------------------------------------
# Pre-compiled regex patterns
# ---------------------------------------------------------------------------
STEP_NUMBER_RE = re.compile(
    r"\b(step|point|number|item)\s+(\d+)\b\s*(?:is|:)?\s*", re.IGNORECASE
)
COMMAND_TRIGGER_RE = re.compile(
    r"\b(new\s+paragraph|new\s+line|line\s+break|next\s+line|"
    r"bullet|dash\s+point|comma|period|full\s+stop|dot|question\s+mark|"
    r"exclamation\s+mark|exclamation\s+point|colon|semicolon|open\s+quote|"
    r"close\s+quote|quote\s+unquote|open\s+parenthesis|close\s+parenthesis|"
    r"open\s+bracket|close\s+bracket|step\s+\d+|point\s+\d+|number\s+\d+|item\s+\d+)\b",
    re.IGNORECASE,
)
ORDINAL_PATTERN = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    r"(?:\s+one)?\s*(?:is|:)?\s+",
    re.IGNORECASE,
)
FAST_PATH_BYPASS_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"step\s+\d+|point\s+\d+|number\s+\d+|item\s+\d+|bullet|new\s+line|"
    r"new\s+paragraph|comma|period|question\s+mark|exclamation\s+mark|"
    r"colon|semicolon|open\s+quote|close\s+quote|open\s+parenthesis|close\s+parenthesis)\b",
    re.IGNORECASE,
)
WHITESPACE_RE = re.compile(r"\s+")
CAP_AFTER_PUNCT_RE = re.compile(r"([.!?]\s+)([a-z])")
PUNCT_SPACING_BEFORE_RE = re.compile(r"\s+([,.;:!?])")
PUNCT_SPACING_AFTER_RE = re.compile(r"([,.;:!?])([A-Za-z])")
PAREN_SPACING_BEFORE_CLOSE_RE = re.compile(r"\s+([\)])")
PAREN_SPACING_AFTER_OPEN_RE = re.compile(r"([\(])\s+")
LINE_SPACING_RE = re.compile(r" *\n *")
BLANK_LINES_RE = re.compile(r"\n{3,}")
LIST_BULLET_PREFIX_RE = re.compile(r"^-\s*")
LIST_NUMBER_PREFIX_RE = re.compile(r"^(\d+)\.\s*")
LINE_PREFIX_RE = re.compile(r"^(\s*(?:-\s+|\d+\.\s+))(.*)$")
QUOTE_LEFT_INNER_SPACE_RE = re.compile(r'"\s+(?=\w)')
QUOTE_RIGHT_INNER_SPACE_RE = re.compile(r'\s+"(?=\s|$|[.,;:!?])')
PAREN_LEFT_INNER_SPACE_RE = re.compile(r"\(\s+")
PAREN_RIGHT_INNER_SPACE_RE = re.compile(r"\s+\)")
NUMBERED_LINE_RE = re.compile(r"^(\d+)[\.)]\s*(.+)$")
TRIM_LIST_BOUNDARY_START_RE = re.compile(r"^[,;:\-\s]+")
TRIM_LIST_BOUNDARY_END_RE = re.compile(r"[,;:\-\s]+$")
TRAILING_CONNECTOR_RE = re.compile(r"\b(and|then)\s*$", re.IGNORECASE)

# Hallucination detection
_HALLUCINATION_INDICATORS = frozenset({
    "you", "i", "uh", "um", "ah", "so", "ok", "thank", "well", "like", "just"
})


# ---------------------------------------------------------------------------
# Hallucination filter
# ---------------------------------------------------------------------------
def filter_hallucinations(text: str) -> str:
    """
    Remove hallucinated patterns that Whisper commonly generates on silence.

    Detects:
    - Any single word appearing > 10% of transcript (repetition loop)
    - > 30% filler/pronoun content
    """
    if not text or len(text.strip()) < 3:
        return text

    words = text.split()
    if not words:
        return text

    total = len(words)

    word_counts: dict[str, int] = {}
    for w in words:
        key = w.lower().rstrip(".,!?;:")
        word_counts[key] = word_counts.get(key, 0) + 1

    if word_counts:
        most_common = max(word_counts, key=word_counts.get)
        if word_counts[most_common] / total > 0.1:
            filtered = [w for w in words if w.lower().rstrip(".,!?;:") != most_common]
            if filtered:
                return filter_hallucinations(" ".join(filtered))
            return ""

    filler_count = sum(
        1 for w in words if w.lower().rstrip(".,!?;:") in _HALLUCINATION_INDICATORS
    )
    if filler_count / total > 0.3:
        real = [w for w in words if w.lower().rstrip(".,!?;:") not in _HALLUCINATION_INDICATORS]
        return " ".join(real) if len(real) >= 3 else ""

    start = next(
        (i for i, w in enumerate(words)
         if w.lower().rstrip(".,!?;:") not in _HALLUCINATION_INDICATORS and len(w.rstrip(".,!?;:")) > 1),
        0,
    )
    end = next(
        (i for i in range(total - 1, -1, -1)
         if words[i].lower().rstrip(".,!?;:") not in _HALLUCINATION_INDICATORS and len(words[i].rstrip(".,!?;:")) > 1),
        total - 1,
    )
    return " ".join(words[start : end + 1]).strip() if start <= end else ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _clean_text(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    text = CAP_AFTER_PUNCT_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)
    return text


def _apply_spoken_commands(text: str) -> str:
    if not COMMAND_TRIGGER_RE.search(text):
        return text
    result = text
    for pattern, replacement in COMPILED_SPOKEN_COMMAND_REPLACEMENTS:
        result = pattern.sub(replacement, result)
    result = STEP_NUMBER_RE.sub(r"\n\2. ", result)
    return result


def _normalize_quotes_and_parentheses(text: str) -> str:
    text = QUOTE_LEFT_INNER_SPACE_RE.sub('"', text)
    text = QUOTE_RIGHT_INNER_SPACE_RE.sub('"', text)
    text = PAREN_LEFT_INNER_SPACE_RE.sub("(", text)
    text = PAREN_RIGHT_INNER_SPACE_RE.sub(")", text)
    return text


def _capitalize_line(line: str) -> str:
    if not line:
        return line
    match = LINE_PREFIX_RE.match(line)
    if match:
        prefix, content = match.group(1), match.group(2)
    else:
        prefix, content = "", line
    content = content.strip()
    if not content:
        return prefix.rstrip()
    content = content[0].upper() + content[1:]
    content = CAP_AFTER_PUNCT_RE.sub(lambda m: m.group(1) + m.group(2).upper(), content)
    return f"{prefix}{content}".rstrip()


def _normalize_structured_text(text: str) -> str:
    t = text.replace("\r\n", "\n")
    t = re.sub(r"[\t ]+", " ", t)
    t = PUNCT_SPACING_BEFORE_RE.sub(r"\1", t)
    t = PUNCT_SPACING_AFTER_RE.sub(r"\1 \2", t)
    t = PAREN_SPACING_BEFORE_CLOSE_RE.sub(r"\1", t)
    t = PAREN_SPACING_AFTER_OPEN_RE.sub(r"\1", t)
    t = LINE_SPACING_RE.sub("\n", t)
    t = BLANK_LINES_RE.sub("\n\n", t)
    t = _normalize_quotes_and_parentheses(t)

    lines = [line.strip() for line in t.strip().split("\n")]
    formatted = []
    for line in lines:
        if not line:
            formatted.append("")
            continue
        line = LIST_BULLET_PREFIX_RE.sub("- ", line)
        line = LIST_NUMBER_PREFIX_RE.sub(r"\1. ", line)
        formatted.append(_capitalize_line(line))

    result = "\n".join(formatted).strip()
    if result and "\n" not in result and result[-1] not in ".!?":
        result += "."
    return result


def _format_ordinal_steps(text: str) -> str:
    matches = list(ORDINAL_PATTERN.finditer(text))
    if len(matches) < 2:
        return text

    items = []
    expected = 1
    for idx, match in enumerate(matches):
        ordinal = match.group(1).lower()
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        raw_value = text[match.end() : next_start]
        value = _clean_text(raw_value)
        value = TRIM_LIST_BOUNDARY_START_RE.sub("", value)
        value = TRIM_LIST_BOUNDARY_END_RE.sub("", value)
        value = TRAILING_CONNECTOR_RE.sub("", value).strip().rstrip(".?!")
        if ORDINAL_ORDER.get(ordinal) != expected or not value:
            break
        items.append(value)
        expected += 1

    if len(items) < 2:
        return text

    intro = _clean_text(text[: matches[0].start()]).rstrip(".:")
    intro_line = f"{intro}:" if intro else "Steps:"
    list_block = "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))
    return f"{intro_line}\n{list_block}"


def _normalize_numbered_lists(text: str) -> str:
    lines = text.split("\n")
    result = []
    expected = 1
    in_block = False
    for line in lines:
        stripped = line.strip()
        m = NUMBERED_LINE_RE.match(stripped)
        if not m:
            in_block = False
            expected = 1
            result.append(line)
            continue
        number = int(m.group(1))
        content = m.group(2).strip()
        if not in_block:
            in_block = True
            expected = 1
        if number != expected:
            number = expected
        result.append(f"{number}. {content}")
        expected += 1
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def format_transcript(text: str) -> str:
    """
    Full formatting pipeline: spoken commands → structure → punctuation → capitalization.
    """
    if not text or not text.strip():
        return ""
    stripped = text.strip()

    # Fast path: plain prose with no formatting commands
    if not FAST_PATH_BYPASS_RE.search(stripped):
        plain = _clean_text(stripped)
        if plain and plain[-1] not in ".!?":
            plain += "."
        return plain

    commanded = _apply_spoken_commands(stripped).strip()

    # Auto-detect ordinal step lists ("first … second … third …")
    if "\n" not in commanded and "- " not in commanded:
        ordinal_formatted = _format_ordinal_steps(commanded)
        if "\n" in ordinal_formatted:
            return _normalize_structured_text(_normalize_numbered_lists(ordinal_formatted))

    return _normalize_structured_text(_normalize_numbered_lists(commanded))


def format_transcript_strict(text: str) -> str:
    """Minimal formatting: normalize whitespace only, preserve everything else."""
    if not text or not text.strip():
        return ""
    return " ".join(text.split())
