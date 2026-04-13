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

## Getting Started

We're excited to have you contribute! Whether it's bug fixes, features, documentation, or translations, your help is welcome.

### Development setup

Everything runs inside the project directory — nothing is installed system-wide.

```bash
# Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/open-whisperflow.git
cd open-whisperflow

# Create a virtual environment and install dependencies
make setup

# Start the menu bar app
make run

# Or start the web UI
make web
```

To pre-download models (optional):

```bash
make download
```

### System Requirements

- **macOS, Windows, or Linux**
- **Python 3.9+**
- **Git**
- **2 GB free disk space** (for models)

On macOS specifically, you'll need Xcode Command Line Tools:

```bash
xcode-select --install
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

**Testing guidelines:**
- Add tests for any **new utility function** in `src/shared/` before submitting a PR
- **Mock external services** (Ollama, Quartz) — tests must pass on CI without a running macOS system
- Use `pytest-mock` for mocking:
  ```python
  def test_ollama_fallback(mocker):
      mocker.patch("src.shared.llm_cleanup.requests.post", side_effect=Exception("Ollama offline"))
      result = clean_text("test", "mail")
      assert result == "test"  # Should fallback to raw text
  ```
- All tests must pass locally before submitting a PR:
  ```bash
  make test && make lint
  ```

---

## Code style

We use [ruff](https://github.com/astral-sh/ruff) for linting and code quality:

```bash
make lint        # check for style issues
```

Key conventions:
- **Line length:** 100 characters
- **Imports:** Automatically sorted (ruff handles this)
- **Type hints:** Encouraged for public functions
- **Docstrings:** Use for complex functions (especially in `src/shared/`)
- **Comments:** Explain *why*, not *what* (code should be self-documenting)

Before submitting a PR, ensure your code is clean:

```bash
ruff check src/ config/  # Check for issues
ruff format src/ config/ # Auto-format
```

---

## Submitting a Pull Request

### Before you submit:

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Test locally:**
   ```bash
   make test && make lint
   ```

3. **Commit with clear messages:**
   ```bash
   git commit -m "Brief description of change"
   ```
   - Use imperative mood ("Add feature" not "Added feature")
   - Reference issues: "Fixes #123" or "Related to #456"
   - Keep commits focused on a single logical change

4. **Push and open a PR:**
   ```bash
   git push origin feature/your-feature-name
   ```

### PR Requirements

Before submitting, ensure:

- [ ] Tests pass: `make test`
- [ ] Code is clean: `make lint`
- [ ] No new dependencies added (discuss first if needed)
- [ ] All file paths stay inside project directory (no `~/.cache`, no system installs)
- [ ] Documentation updated (if applicable)
- [ ] PR title is descriptive
- [ ] PR description explains *why* this change is needed

### PR Checklist Template

Include this in your PR description:

```markdown
## What does this PR do?
Brief description of changes.

## Why?
What problem does this solve?

## Testing
How can reviewers test this?

## Related Issues
Fixes #123
```

### Code Review

We review PRs promptly. Common feedback points:

- **Performance:** Does this impact startup time or memory?
- **Privacy:** Does this send data outside the project folder?
- **Compatibility:** Does this work on all supported Python versions?
- **Tests:** Are there test cases covering the new code?
- **Documentation:** Is the change documented (docstrings, README, etc.)?

It's normal to have back-and-forth on a PR — we're here to help!

---

## Reporting Issues

Found a bug or have a feature idea? Please open a [GitHub Issue](https://github.com/open-whisperflow/open-whisperflow/issues).

### Bug Reports

Include:
- **OS & Python version:** `python3 --version` and your OS
- **Steps to reproduce:** Clear steps that trigger the bug
- **Actual vs. expected behavior**
- **Error message/traceback** (if applicable)
- **Your Whisper model and Python version**

**Example:**

```
## Environment
- macOS 13.5
- Python 3.11.2
- Whisper model: base

## Steps to reproduce
1. Run `make run`
2. Hold Fn key
3. Speak "test this out"
4. Release Fn

## Expected
Text pasted into active app

## Actual
Error in terminal: "AudioInterface: Failed to initialize..."

## Traceback
[paste full error here]
```

### Feature Requests

Describe:
- **What you want to achieve:** The use case or problem
- **Proposed solution:** Your idea (if you have one)
- **Why it matters:** Why would this help other users?

**Example:**

```
## Use Case
I dictate long documents and want to pause/resume without stopping the app.

## Proposed Solution
Add a "pause" hotkey separate from the recording hotkey.

## Why
Currently I have to release Fn and wait for transcription, then hold again to continue. Native pause would be faster.
```

### Before Opening an Issue

1. **Check existing issues** — Your issue might already be reported or fixed
2. **Search closed issues** — The fix might be in a newer version
3. **Verify your setup** — Run `make test` to rule out a broken install
4. **Check docs** — Your question might be answered in [docs/INSTALLATION.md](docs/INSTALLATION.md)
5. **Try troubleshooting** — See [README.md troubleshooting section](../README.md#troubleshooting)

---

## Architecture & Key Design Decisions

### Self-Contained by Design
Everything — models, cache, history, settings — lives inside the project folder. Nothing is written to `~/.cache`, `~/.config`, or any system location. This is enforced by `config/config.py`.

This approach ensures:
- **Privacy:** All data stays in the project folder
- **Portability:** Works without system configuration
- **Cleanup:** Simply delete the folder to remove everything

### Why faster-whisper, not openai-whisper?

We use `faster-whisper` exclusively because:
- **4-8x faster** than `openai-whisper` (using `int8` quantization)
- **Lower memory** usage on typical machines
- **Better macOS support** (especially Apple Silicon)

### Apple Silicon (M1/M2/M3) Note

`ctranslate2` (used by faster-whisper) doesn't support Metal Performance Shaders (MPS) on Apple Silicon. Instead:
- We use `compute_type="int8"` on CPU for ARM NEON optimization
- This is still much faster than `openai-whisper`
- Fallback: Use `compute_type="float32"` for maximum compatibility (slower but reliable)

### Optional Ollama Integration

LLM cleanup gracefully falls back to raw transcription if Ollama isn't running:

```python
try:
    cleaned = clean_text(raw_transcription, app_context)
except requests.exceptions.ConnectionError:
    cleaned = raw_transcription  # Fallback
```

This keeps the core experience working even without the optional Ollama server.

---

## Areas for Contribution

### 🎯 High Impact (especially welcome!)

- **Performance improvements** — Faster initialization, reduced memory usage
- **macOS fixes** — Accessibility permissions, hotkey reliability
- **Web UI enhancements** — Mobile responsiveness, copy-paste UX
- **Language support** — Translations, language-specific formatting
- **Testing** — More test coverage, especially edge cases
- **Documentation** — Clearer guides, troubleshooting, use case examples

### 📚 Documentation

- Writing guides for specific use cases (coding, writing, emails)
- Improving troubleshooting sections
- Adding video tutorials or GIFs
- Translating docs to other languages

### ⚙️ Code Improvements

- Type annotations for `src/shared/` modules
- Performance profiling and optimization
- Better error messages
- Refactoring complex functions

### 🧪 Testing

Areas with gaps:
- `src/shared/formatter.py` — Spoken command parsing
- `src/shared/llm_cleanup.py` — With mocked Ollama
- macOS app lifecycle (startup, shutdown, hotkey detection)
- Web app file upload handling

### 🌍 Translations & Localization

Help translate WhisperFlow for other regions:
- UI messages and menu labels
- Documentation (README, INSTALLATION, etc.)
- Whisper language packs optimization

---

## Questions?

Have questions about contributing? 
- Ask in [GitHub Discussions](https://github.com/open-whisperflow/open-whisperflow/discussions)
- Email or open a GitHub issue with the `question` label

We're here to help! 🙌
