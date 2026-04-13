# Changelog

All notable changes to RoastMyAudio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open-source release planning

### Coming Soon
- Streaming transcription (real-time output as you speak)
- Enhanced voice activity detection (VAD) for better silence trimming
- Custom Whisper model support (ability to load fine-tuned models)
- Batch transcription (transcribe multiple audio files)
- Language auto-detection (detect language from audio)
- Keyboard shortcut customization UI
- Transcription statistics dashboard
- Export to various formats (PDF, Word, Markdown)

---

## [0.1.0] - 2026-04-13

### Initial Release

#### Added

**Core Features**
- ✅ Fully local speech-to-text using OpenAI Whisper
- ✅ No cloud services, no subscriptions, no telemetry
- ✅ Support for 10 languages (EN, ES, FR, DE, ZH, JA, PT, IT, KO, RU)
- ✅ All Whisper models (tiny → large-v3, 40MB → 3GB)

**macOS Menu Bar App**
- ✅ Global hotkey detection (Fn key, fallback Ctrl+Option+D)
- ✅ Live preview overlay showing real-time transcription
- ✅ Automatic text injection into focused applications
- ✅ Menu bar icon with quick settings
- ✅ Model and language selection from app menu
- ✅ Auto-start at login (optional)
- ✅ Microphone access with fallback detection

**Web Interface (All Platforms)**
- ✅ Browser-based dictation (works on Windows, macOS, Linux)
- ✅ Single-page application with responsive design
- ✅ Model selector and language chooser
- ✅ Live transcription preview
- ✅ Formatted vs. raw text view toggle
- ✅ Local browser storage for transcription history

**Text Processing**
- ✅ Spoken command recognition ("new line", "period", "bullet point", etc.)
- ✅ Intelligent punctuation rules
- ✅ Numbered/bulleted list formatting
- ✅ Hallucination detection and filtering
- ✅ Optional Ollama LLM integration for grammar cleanup
- ✅ Custom word dictionary for domain-specific terms

**Data Management**
- ✅ Transcription history (stored locally, max 500 entries)
- ✅ Settings persistence (user preferences saved in data/settings.json)
- ✅ Custom dictionary for domain-specific vocabulary
- ✅ All data stored locally in project folder (no external databases)

**Developer Experience**
- ✅ Unified Makefile for common tasks
- ✅ Modern Python tooling (ruff linting, pytest testing)
- ✅ Comprehensive documentation (README, CONTRIBUTING, INSTALLATION, ARCHITECTURE)
- ✅ Self-contained environment (virtual env, no system installations)
- ✅ Relative paths (works on any machine)
- ✅ Example test suite with pytest

**Architecture**
- ✅ Shared transcription logic between macOS and web apps
- ✅ Model caching and in-memory optimization
- ✅ Audio preprocessing and silence trimming (Silero VAD)
- ✅ Thread-safe model loading and inference
- ✅ Graceful Ollama degradation (works without it)

#### Technical Stack

**Audio & ML**
- faster-whisper (4-8x faster than openai-whisper)
- torch / torchaudio for on-device ML
- sounddevice for audio capture
- Silero VAD for voice activity detection

**Frontend**
- Flask web framework
- HTML5 / CSS3 responsive design
- Plain JavaScript (no framework dependencies)
- Local browser storage for history

**macOS-Specific**
- PyObjC for native framework integration
- rumps for menu bar app
- pynput for global hotkey detection
- Quartz for accessibility APIs

**Development**
- pytest for unit testing
- ruff for code linting and formatting
- python-dotenv for environment configuration

#### Documentation

- **README.md** — Feature overview and quick start
- **docs/INSTALLATION.md** — Step-by-step setup for all platforms
- **docs/ARCHITECTURE.md** — Technical design and module documentation
- **CONTRIBUTING.md** — Developer contribution guidelines
- **CODE_OF_CONDUCT.md** — Community standards
- **LICENSE** — MIT license
- **CHANGELOG.md** — This file

#### Known Limitations

- **macOS only for menu bar app** (by design; web app works on all platforms)
- **Global hotkey on macOS requires accessibility permissions** (required for Fn key detection)
- **Windows batch scripts not included** (web app works fine on Windows via make/bash)
- **No executable installer** (run from source or wrap in your favorite tool)
- **Apple Silicon (M1/M2/M3) uses CPU int8** (MPS not supported by ctranslate2 yet)

#### Testing

- Unit tests for text formatting (formatter.py)
- Unit tests for LLM cleanup (llm_cleanup.py with mocked Ollama)
- Unit tests for transcription history
- CI/CD ready (tests run on any platform)

---

## Future Versions (Roadmap)

### 0.2.0 (Planned)
- [ ] Streaming transcription for real-time output
- [ ] Custom model path support
- [ ] Keyboard shortcut customization
- [ ] Improved UI styling

### 0.3.0 (Planned)
- [ ] Batch transcription
- [ ] Language auto-detection
- [ ] Export to PDF, Word, Markdown
- [ ] Audio file upload support

### 1.0.0 (Planned)
- [ ] Stable API and settings format
- [ ] Extended language support
- [ ] Performance optimizations
- [ ] Comprehensive plugin system

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for details on:
- How to report bugs
- How to suggest features
- How to submit pull requests

---

## Support

- 🐛 **Found a bug?** Open a [GitHub Issue](https://github.com/roastmyaudio/roastmyaudio/issues)
- 📚 **Need help?** Check [docs/INSTALLATION.md](docs/INSTALLATION.md)
- 💬 **Have questions?** See [README.md](README.md#support) or open a Discussion
- ⭐ **Like this project?** Please star it on GitHub!

---

## License

MIT License — see [LICENSE](LICENSE) for details.
