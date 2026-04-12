# Contributing to WhisperFlow

Thank you for your interest in contributing! This document covers everything you need to get started.

## Table of Contents

- [Development setup](#development-setup)
- [Project structure](#project-structure)
- [Making changes](#making-changes)
- [Tests](#tests)
- [Code style](#code-style)
- [Submitting a pull request](#submitting-a-pull-request)
- [Reporting issues](#reporting-issues)

---

## Development setup

Everything runs inside the project directory — nothing is installed system-wide.

```bash
git clone https://github.com/your-username/open-whisperflow
cd open-whisperflow

make setup   # creates .venv, installs all deps
make run     # start the menu bar app
make web     # start the web UI
```

To pre-download models:

```bash
make download
```

---

## Project structure

```
src/
  shared/               # Cross-platform utilities
    formatter.py        # Text formatting (spoken commands, punctuation)
    transcriber.py      # faster-whisper transcription engine
    llm_cleanup.py      # Ollama LLM cleanup (optional)
    text_injector.py    # macOS text injection via Cmd+V
    settings.py         # Persistent user settings (data/settings.json)
    dictionary.py       # Custom word dictionary
    history.py          # Transcription history
  apps/
    macos/              # macOS menu bar app
      menubar_dictation.py   # Main app (rumps orchestrator)
      hud_overlay.py         # NSWindow HUD overlay
      audio_recorder.py      # sounddevice capture wrapper
      warmup.py              # Startup model preloading
    web/                # Flask web UI
      app.py
      templates/
      static/

config/
  config.py             # Centralized paths and settings

tests/                  # pytest test suite
scripts/                # Setup and utility scripts
```

---

## Making changes

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/my-improvement
   ```

2. **Read the code** before changing it. The key shared modules are in `src/shared/`.

3. **Keep changes focused.** Fix one thing per PR. If you find unrelated improvements, open a separate PR.

4. **Shared modules first.** If you're adding transcription logic, add it to `src/shared/transcriber.py` so both the macOS app and web UI can use it.

---

## Tests

Run the full test suite with:

```bash
make test
```

Or run a specific test file:

```bash
.venv/bin/pytest tests/test_formatter.py -v
```

**Guidelines:**
- Add tests for any new utility function in `src/shared/`
- Mock external services (Ollama, Quartz) — tests must pass on CI without a running Mac
- Use `pytest-mock` for mocking

---

## Code style

We use [ruff](https://github.com/astral-sh/ruff) for linting:

```bash
make lint        # check for issues
make lint-fix    # auto-fix where possible
```

Key rules:
- Line length: 100 characters
- Imports: sorted (ruff handles this automatically)
- No unused imports
- Type annotations encouraged but not required

---

## Submitting a pull request

1. Make sure `make test` and `make lint` both pass
2. Keep the PR description concise — what changed and why
3. Reference any related issues (`Fixes #123`)
4. One logical change per PR — avoid bundling unrelated fixes

**PR checklist:**
- [ ] Tests pass (`make test`)
- [ ] Linter is clean (`make lint`)
- [ ] All paths stay inside the project directory (no `~/.cache`, no system installs)
- [ ] Models still cache to `cache/models/`
- [ ] No new dependencies added without discussion

---

## Reporting issues

Use [GitHub Issues](https://github.com/your-username/open-whisperflow/issues) with the appropriate template:

- **Bug report** — something isn't working
- **Feature request** — an idea for improvement

**Before opening a bug report:**
1. Check existing issues to avoid duplicates
2. Run `make test` to rule out a setup problem
3. Include your macOS version, Python version, and the exact error message

---

## Architecture notes

- **Self-contained by design.** Everything — models, cache, history, settings — lives inside the project folder. Nothing is written to `~/.cache` or any system location. This is enforced by `config/config.py`.
- **faster-whisper, not openai-whisper.** We use `faster-whisper` exclusively for 4-8x speed and `int8` quantization.
- **No ctranslate2 MPS on macOS.** Apple Silicon users benefit from ARM NEON via `compute_type="int8"` on CPU. MPS is not supported by ctranslate2.
- **Optional Ollama.** LLM cleanup gracefully falls back to raw transcription if Ollama isn't running.
