"""Durable drafts, theme and onboarding, independent of browser/server origin."""

import json

from config import DATA_DIR
from src.shared.storage import synchronized, write_json

WORKSPACE_PATH = DATA_DIR / "workspace.json"
DEFAULTS = {"draft": "", "theme": "light", "onboarding_complete": False}


@synchronized(lambda: WORKSPACE_PATH)
def load():
    try:
        value = json.loads(WORKSPACE_PATH.read_text())
        return {**DEFAULTS, **{key: value[key] for key in DEFAULTS if key in value}}
    except (OSError, ValueError, TypeError):
        return dict(DEFAULTS)


@synchronized(lambda: WORKSPACE_PATH)
def update(values, only_if_empty=False):
    if not isinstance(values, dict) or any(key not in DEFAULTS for key in values):
        raise ValueError("Unknown workspace preference")
    if "draft" in values and (
        not isinstance(values["draft"], str) or len(values["draft"]) > 2_000_000
    ):
        raise ValueError("Draft must contain at most two million characters")
    if "theme" in values and (
        not isinstance(values["theme"], str) or values["theme"] not in {"light", "dark"}
    ):
        raise ValueError("Choose light or dark appearance")
    if "onboarding_complete" in values and type(values["onboarding_complete"]) is not bool:
        raise ValueError("Invalid onboarding preference")
    current = load()
    if only_if_empty:
        values = {
            key: value for key, value in values.items() if key == "draft" and not current["draft"]
        }
    current.update(values)
    write_json(WORKSPACE_PATH, current)
    return current
