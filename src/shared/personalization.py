"""Explicit correction pairs, spoken snippets and application style preferences."""

import json
import re

from config import DATA_DIR
from src.shared.storage import synchronized, write_json

PERSONALIZATION_PATH = DATA_DIR / "personalization.json"
DEFAULTS = {"corrections": [], "snippets": [], "app_styles": []}
STYLES = {"default", "verbatim", "formal", "casual", "concise", "bullets"}


@synchronized(lambda: PERSONALIZATION_PATH)
def load():
    try:
        value = json.loads(PERSONALIZATION_PATH.read_text())
        return {key: value.get(key, []) for key in DEFAULTS}
    except (OSError, ValueError, TypeError, AttributeError):
        return {key: [] for key in DEFAULTS}


@synchronized(lambda: PERSONALIZATION_PATH)
def save(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError("Provide corrections, snippets and app styles")
    schemas = {
        "corrections": ("heard", "write"),
        "snippets": ("trigger", "text"),
        "app_styles": ("app", "style"),
    }
    result = {}
    for group, fields in schemas.items():
        rows = value[group]
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Each library supports up to 100 entries")
        seen = set()
        result[group] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(fields):
                raise ValueError("Invalid personalization entry")
            cleaned = {key: row[key].strip() if isinstance(row[key], str) else "" for key in fields}
            if any(not text or len(text) > 10_000 for text in cleaned.values()):
                raise ValueError("Entries need nonempty text of at most 10,000 characters")
            key = cleaned[fields[0]].casefold()
            if key in seen:
                raise ValueError("Remove duplicate entries")
            seen.add(key)
            if group == "app_styles" and cleaned["style"] not in STYLES:
                raise ValueError("Unsupported application style")
            result[group].append(cleaned)
    write_json(PERSONALIZATION_PATH, result)
    return result


def apply(text, library=None):
    library = library if library is not None else load()
    trigger = text.strip().rstrip(".!?").casefold()
    for row in library["snippets"]:
        if row["trigger"].casefold() == trigger:
            return row["text"], True
    for row in library["corrections"]:
        text = re.sub(
            r"(?<!\w)" + re.escape(row["heard"]) + r"(?!\w)",
            lambda _, replacement=row["write"]: replacement,
            text,
            flags=re.IGNORECASE,
        )
    return text, False


def style_for(app_name, library=None):
    library = library if library is not None else load()
    return next(
        (
            row["style"]
            for row in library["app_styles"]
            if row["app"].casefold() == app_name.casefold()
        ),
        "default",
    )
