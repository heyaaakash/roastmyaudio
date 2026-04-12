# Changelog

All notable changes to WhisperFlow are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- `src/shared/formatter.py` — extracted text formatting into a standalone shared module (spoken commands, punctuation, capitalization, ordinal step lists)
- `src/shared/transcriber.py` — new faster-whisper transcription engine shared by both the macOS app and web UI
- `src/shared/settings.py` — persistent JSON settings (`data/settings.json`) for model, language, hotkey, and LLM toggle
- `src/apps/macos/hud_overlay.py` — extracted `DictationOverlay` NSWindow class from main app file
- `src/apps/macos/audio_recorder.py` — extracted `AudioRecorder` sounddevice wrapper and audio normalization utilities
- `Makefile` — `make setup`, `make run`, `make web`, `make test`, `make lint`, `make bundle`
- `pyproject.toml` — modern Python packaging with ruff and pytest configuration
- `requirements-dev.txt` — separate dev dependencies (ruff, pytest, pytest-mock)
- `tests/` — pytest test suite covering formatter, LLM cleanup, text injection, config, and settings
- `CONTRIBUTING.md` — contributor guide with setup, testing, and code style instructions
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1
- `.github/workflows/ci.yml` — GitHub Actions CI: runs pytest + ruff on every PR
- `.github/ISSUE_TEMPLATE/` — bug report and feature request templates
- `.github/PULL_REQUEST_TEMPLATE.md` — PR checklist
- `scripts/install_launch_agent.sh` — generates and loads a launchd plist for auto-start at login
- Language selector now covers 10 languages (was English-only)
- LLM Cleanup toggle in the menu bar (persisted to settings)

### Changed
- **Switched from `openai-whisper` to `faster-whisper` exclusively** — 4-8x faster, uses `int8` quantization, lower memory footprint
- `src/apps/web/app.py` — simplified to use shared `transcriber` and `formatter` modules; removed inline duplicated code
- `src/apps/macos/warmup.py` — fixed broken imports (was pointing at old `web_mvp` path)
- `src/apps/macos/menubar_dictation.py` — refactored from 1545 lines to ~550 lines by extracting modules; now uses shared transcription engine
- `config/config.py` — added `HF_HOME` Python variable and `SETTINGS_PATH`
- `requirements.txt` — removed `openai-whisper`, `whisperx`, `pywebview`, `torchaudio`, `transformers`, `silero-vad` (now handled by faster-whisper's built-in VAD)
- Links updated from `openai/whisper` to project repository

### Removed
- Stale duplicate files in `src/apps/macos/`: `dictionary.py`, `history.py`, `llm_cleanup.py`, `text_injector.py`, `download_model.py`, `download_model_v2.py`, `main.py` (all superseded by `src/shared/` counterparts)
- Inline `_DictationOverlay`, `_filter_hallucinations`, `trim_silence`, `_normalize_audio_for_quiet_speech_static` from `menubar_dictation.py`

### Fixed
- `warmup.py` was importing from non-existent `web_mvp.app` path

---

## [0.0.1] — Initial release

- macOS menu bar push-to-talk dictation with Fn key
- Local Whisper transcription (turbo model by default)
- Silero VAD for silence trimming
- Optional Ollama LLM cleanup
- Text injection via Cmd+V
- Live preview HUD overlay
- Flask web UI for browser-based transcription
- Fully self-contained: all models and data in project directory
