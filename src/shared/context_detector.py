"""
Context Detection and Vocabulary Injection for RoastMyAudio.

Provides intelligent context-awareness:
1. Identifies the active application and maps it to domain modes (Code, Chat, Email/Doc, General).
2. Sniffs the system clipboard for technical tokens (camelCase, snake_case, identifiers, APIs).
3. Injects domain-specific vocabulary and prompt hints into Whisper for 100% spelling accuracy.
4. Provides context-conditioned prompt instructions for local LLM cleanup.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Application Mode Classifications
# ---------------------------------------------------------------------------
MODE_CODE = "code"
MODE_CHAT = "chat"
MODE_EMAIL_DOC = "email_doc"
MODE_GENERAL = "general"

APP_CATEGORIES: dict[str, list[str]] = {
    MODE_CODE: [
        "code", "cursor", "xcode", "terminal", "iterm", "pycharm",
        "intellij", "clion", "webstorm", "android studio", "sublime text",
        "vim", "nvim", "neovim", "emacs", "nova", "warp", "ghostty",
        "alacritty", "kitty", "zed", "visual studio", "textmate",
    ],
    MODE_CHAT: [
        "slack", "discord", "messages", "telegram", "whatsapp",
        "teams", "signal", "wechat", "mattermost", "element", "zoom",
    ],
    MODE_EMAIL_DOC: [
        "mail", "outlook", "notion", "obsidian", "google docs", "notes",
        "linear", "jira", "pages", "word", "superhuman", "spark",
        "bear", "craft", "confluence", "asana", "trello",
    ],
}

# Domain vocabulary hints injected into Whisper initial_prompt
DOMAIN_VOCABULARY: dict[str, list[str]] = {
    MODE_CODE: [
        "API", "JSON", "async", "await", "function", "variable", "const",
        "return", "class", "git", "commit", "branch", "repo", "PR", "merge",
        "Docker", "Kubernetes", "SQL", "frontend", "backend", "endpoint",
        "boolean", "string", "integer", "null", "undefined", "import", "export",
        "Python", "TypeScript", "JavaScript", "Rust", "Golang", "C++",
    ],
    MODE_CHAT: [
        "hey", "thanks", "sounds good", "LGTM", "ping me", "let's sync",
        "catch you later", "BRB", "FYI", "awesome", "got it", "sure thing",
    ],
    MODE_EMAIL_DOC: [
        "Regards", "Sincerely", "Following up", "As discussed", "Action items",
        "Deliverables", "Timeline", "Summary", "Overview", "Next steps",
        "Key takeaways", "Meeting notes", "Proposal", "Objectives",
    ],
    MODE_GENERAL: [
        "Whisper", "dictation", "transcription", "audio", "recording",
    ],
}

# Regex for extracting programming identifiers from clipboard
# Matches camelCase, PascalCase, snake_case, UPPER_CASE, dot.notation, function()
_TOKEN_PATTERN = re.compile(
    r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:[.\-][a-zA-Z0-9_]+)+\b|"  # dot.notation / hyphen-names
    r"\b[a-z]+(?:[A-Z][a-z0-9]+)+\b|"                       # camelCase
    r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b|"               # PascalCase
    r"\b[a-zA-Z]+_[a-zA-Z0-9_]+\b|"                         # snake_case
    r"\b[A-Z]{2,}(?:_[A-Z0-9]+)*\b"                         # CONSTANT_CASE
)


# ---------------------------------------------------------------------------
# Context Detection Helpers
# ---------------------------------------------------------------------------
def get_app_mode(app_name: Optional[str]) -> str:
    """
    Classify frontmost app into 'code', 'chat', 'email_doc', or 'general'.
    """
    if not app_name:
        return MODE_GENERAL

    app_lower = app_name.lower().strip()
    for mode, keywords in APP_CATEGORIES.items():
        for kw in keywords:
            if kw in app_lower:
                return mode
    return MODE_GENERAL


def extract_clipboard_keywords(clipboard_text: Optional[str], max_tokens: int = 12) -> list[str]:
    """
    Extract meaningful identifiers and technical tokens from clipboard text.
    Filters out common noise and caps total tokens.
    """
    if not clipboard_text or not clipboard_text.strip():
        return []

    # Limit scanning to first 2000 chars to remain fast
    snippet = clipboard_text[:2000]
    matches = _TOKEN_PATTERN.findall(snippet)

    seen = set()
    tokens = []
    for token in matches:
        token_clean = token.strip()
        # Keep sensible length tokens (3 to 45 chars)
        if 3 <= len(token_clean) <= 45 and token_clean not in seen:
            seen.add(token_clean)
            tokens.append(token_clean)
            if len(tokens) >= max_tokens:
                break

    return tokens


def build_whisper_prompt(
    app_name: Optional[str] = None,
    clipboard_text: Optional[str] = None,
    custom_words: Optional[list[str]] = None,
    max_prompt_len: int = 240,
) -> str:
    """
    Build a rich initial_prompt for Whisper that biases transcription accuracy
    towards active app vocabulary, clipboard tokens, and user dictionary words.
    """
    prompt_parts: list[str] = []

    # 1. Custom dictionary words (highest priority)
    if custom_words:
        for w in custom_words:
            w_str = str(w).strip()
            if w_str and w_str not in prompt_parts:
                prompt_parts.append(w_str)

    # 2. Clipboard tokens (high priority for active coding/copy-paste work)
    clip_tokens = extract_clipboard_keywords(clipboard_text, max_tokens=10)
    for token in clip_tokens:
        if token not in prompt_parts:
            prompt_parts.append(token)

    # 3. Domain vocabulary for active app
    mode = get_app_mode(app_name)
    domain_words = DOMAIN_VOCABULARY.get(mode, DOMAIN_VOCABULARY[MODE_GENERAL])
    for dw in domain_words:
        if dw not in prompt_parts:
            prompt_parts.append(dw)

    # Join and enforce prompt length limit
    result = ", ".join(prompt_parts)
    if len(result) > max_prompt_len:
        # Truncate at last comma within limit
        cut = result[:max_prompt_len]
        last_comma = cut.rfind(",")
        if last_comma > 20:
            result = cut[:last_comma]
        else:
            result = cut

    return result.strip().rstrip(",") + "." if result else ""


def get_llm_mode_guidance(app_name: Optional[str] = None) -> str:
    """
    Return context-specific guidance for embedded LLM cleanup.
    """
    mode = get_app_mode(app_name)
    if mode == MODE_CODE:
        return (
            "Context: Code Editor / Terminal. Preserve exact code identifiers, "
            "function names, camelCase, snake_case, variable names, and syntax."
        )
    elif mode == MODE_CHAT:
        return (
            "Context: Team Chat / Messaging. Keep tone conversational, natural, "
            "and concise."
        )
    elif mode == MODE_EMAIL_DOC:
        return (
            "Context: Email / Document. Format with professional punctuation, "
            "clear sentence structure, and clean paragraph breaks."
        )
    return "Context: General. Professional and clear formatting."
