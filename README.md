# 🎙️ RoastMyAudio

> **Open-source, fully local speech-to-text for every device**

RoastMyAudio is a privacy-first dictation engine powered by OpenAI's [Whisper](https://openai.com/research/whisper). Run it on **macOS** (menu bar app) or **any OS** (web browser). Nothing leaves your machine. No subscriptions. No cloud. No telemetry.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-green.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## Use Cases

### 🖥️ macOS Menu Bar App
Hold a key, speak, release — text pastes anywhere instantly.

```
Hold Fn  →  speak  →  release  →  text pasted into any app
```

- **Live preview** of words while you speak
- **One-key push-to-talk** (hold `Fn` or `Ctrl+Option+D`)
- **Instant text injection** via Cmd+V
- Perfect for emails, Slack, notes, code comments

### 🌐 Web App (macOS, Windows, Linux)
Open a browser tab and start dictating.

```
http://127.0.0.1:5000  →  record  →  transcribed text in browser
```

- Works on **any OS** (Windows, Mac, Linux)
- Use on multiple devices sharing the same computer
- Copy-paste results or integrate with other tools
- No native app required

---

## Why RoastMyAudio?

| Feature | RoastMyAudio | Wispr Flow | Google Docs | VS Code Voice |
|---------|------------|-----------|-----------|--------------|
| **Local transcription** | ✅ | ✅ | ❌ (cloud) | ❌ (cloud) |
| **No subscription** | ✅ | ❌ ($10/mo) | ✅ (free) | ✅ (free) |
| **Works offline** | ✅ | ❌ | ❌ | ❌ |
| **No telemetry** | ✅ | ❌ | ❌ | ❌ |
| **Open source** | ✅ | ❌ | ❌ | ❌ |
| **LLM grammar cleanup** | ✅ (Ollama) | ✅ | ✅ | ✅ |
| **Spoken commands** | ✅ | ✅ | ✅ | ❌ |
| **macOS menu bar** | ✅ | ✅ | ❌ | ❌ |
| **Web browser** | ✅ | ❌ | ✅ | ❌ |

---

## Quick Start

### macOS Menu Bar (Recommended)

```bash
# Clone and setup
git clone https://github.com/roastmyaudio/roastmyaudio
cd roastmyaudio

make setup   # creates .venv, installs deps locally
make run     # launches menu bar app
```

That's it. Hold `Fn` to start speaking.

**Optional: Pre-download models** (saves waiting on first use)

```bash
make download
```

**Optional: Start at login**

```bash
bash scripts/install_launch_agent.sh
```

### Web App (All Operating Systems)

```bash
make setup   # once
make web     # start server
```

Then open **http://127.0.0.1:5000** in your browser.

---

## Features

### Core
- ✅ **Real-time speech-to-text** — Uses OpenAI Whisper (10 languages)
- ✅ **Whisper model selector** — `tiny` (40 MB) to `large-v3` (3 GB)
- ✅ **Spoken commands** — Say "new line", "period", "comma" → they appear as formatting
- ✅ **Custom dictionary** — Add domain-specific terms (e.g., "Kubernetes", "GraphQL")
- ✅ **Transcription history** — Recent transcriptions saved locally

### macOS Menu Bar Only
- ✅ **Push-to-talk** — Hold `Fn` (or `Ctrl+Option+D` fallback)
- ✅ **Live preview overlay** — See words appear as you speak
- ✅ **Automatic text injection** — Results pasted via Cmd+V into any app
- ✅ **Menu bar quick settings** — Change model, language from top bar icon
- ✅ **Launch at login** — Optional auto-start

### Web App
- ✅ **Browser recording** — Works on any OS
- ✅ **Model selection dropdown** — Choose transcription speed vs. accuracy
- ✅ **Copy to clipboard** — One-click results export
- ✅ **Responsive design** — Desktop, tablet, and mobile friendly

### Optional Enhancements
- ✅ **LLM cleanup** — Run local [Ollama](https://ollama.ai) to fix grammar and remove filler words
- ✅ **Environment variable config** — Override settings without editing code

---

## Privacy & Security

**All processing happens on your computer:**

- 🔐 Models stored in `cache/models/` (local project folder)
- 📝 History saved in `data/history.json` (local project folder)
- ⚙️ Settings in `data/settings.json` (local project folder)
- 🌐 **Zero external API calls** (except optional Ollama, which also runs locally)
- 🚫 **No telemetry, analytics, or crash reporting**

**Internet required only for:**
- Initial model download (one-time, ~140 MB for `base` model)
- Optional Ollama LLM integration (runs on `localhost:11434`)

---

## System Requirements

### macOS Menu Bar App
- **macOS 11+** (Big Sur or later)
- **Python 3.9+**
- **2 GB+ free disk** (for models; 140 MB minimum with `tiny` model)
- **2–8 GB RAM** (depends on model size; `tiny` needs ~1 GB, `base` needs ~2-3 GB)

### Web App
- **macOS, Windows, or Linux**
- **Python 3.9+**
- **Modern browser** with microphone access (Chrome, Firefox, Safari, Edge)
- **2 GB+ free disk**

Check your Python version:

```bash
python3 --version   # Should output 3.9 or higher
```

---

## Commands

```bash
make setup      # Create .venv and install all dependencies
make run        # Start macOS menu bar app
make web        # Start web UI (http://127.0.0.1:5000)
make download   # Download Whisper models interactively
make test       # Run test suite
make lint       # Check code style (ruff)
make clean      # Remove .venv and cached files
```

---

## Configuration

Settings auto-save when changed in the app menu. You can also override via environment variables:

```bash
export WHISPER_MODEL=small            # tiny, base (default), small, medium, large
export WHISPER_LANGUAGE=es            # en (default), es, fr, de, zh, ja, pt, it, ko, ru
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=llama3.2:1b       # Requires Ollama running locally
```

Or create `config/.env` and add these variables:

```bash
WHISPER_MODEL=small
WHISPER_LANGUAGE=en
```

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for detailed setup and troubleshooting.

---

## Documentation

- **[Installation Guide](docs/INSTALLATION.md)** — Detailed setup for both platforms
- **[Architecture](docs/ARCHITECTURE.md)** — How RoastMyAudio works internally
- **[Contributing](CONTRIBUTING.md)** — How to contribute or report bugs
- **[Code of Conduct](CODE_OF_CONDUCT.md)** — Community guidelines

---

## Project Structure

```
src/
  apps/
    macos/              # Menu bar app (macOS only)
      menubar_dictation.py
      audio_recorder.py
      hud_overlay.py
    web/                # Web app (all OS)
      app.py
      static/, templates/
  shared/               # Cross-platform modules
    transcriber.py      # Whisper transcription engine
    formatter.py        # Spoken command & text formatting
    llm_cleanup.py      # Optional Ollama grammar fix
    text_injector.py    # macOS text injection
    dictionary.py       # Custom word dictionary
    history.py          # Transcription history
    settings.py         # Configuration management
config/
  config.py             # Centralized settings & paths
docs/
  INSTALLATION.md       # Setup & troubleshooting
  ARCHITECTURE.md       # Technical design
data/                   # Auto-created at runtime
  history.json          # Transcription log
  settings.json         # User preferences
cache/
  models/               # Downloaded Whisper models
```

---

## Troubleshooting

**Q: Models not downloading?**  
Models download automatically to `cache/models/` on first use. If interrupted, delete `cache/models/` and try again.

**Q: Menu bar app not responding to Fn key?**  
1. Grant accessibility permissions: **System Preferences → Security & Privacy → Accessibility**
2. Restart the app
3. Fallback hotkey is `Ctrl+Option+D`

**Q: Web app won't open in browser?**  
Ensure `http://127.0.0.1:5000` is not blocked by antivirus or firewall.

**Q: How do I use Ollama for grammar cleanup?**  
1. Install [Ollama](https://ollama.ai)
2. Run `ollama pull llama3.2:1b` to download a lightweight model
3. Start Ollama (runs on `localhost:11434` by default)
4. RoastMyAudio will auto-detect and use it

See [docs/INSTALLATION.md](docs/INSTALLATION.md#troubleshooting) for more help.

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Reporting bugs
- Suggesting features
- Setting up a development environment
- Submitting pull requests

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Support

💬 **Questions or issues?**
- Open a [GitHub Issue](https://github.com/roastmyaudio/roastmyaudio/issues)
- Check [docs/](docs/) for detailed docs
- Review [CONTRIBUTING.md](CONTRIBUTING.md) for setup help

**Like this project?** Please ⭐ it on GitHub!

---

## macOS permissions

The app needs three permissions on first launch:

1. **Microphone** — to capture your voice
2. **Input Monitoring** — to detect the `Fn` key globally
3. **Accessibility** — to inject text into other apps

macOS will prompt for these automatically. If something breaks, go to **System Settings → Privacy & Security** and grant access to Terminal or your Python process.

---

## Requirements

- macOS 12+ (Monterey or later)
- Python 3.9–3.12
- ~500 MB disk space for the default base model
- 4 GB RAM recommended (16 GB for large-v3)

---

## Architecture

```
src/
  shared/               # Used by both macOS app and web UI
    transcriber.py      # faster-whisper engine (int8, CPU)
    formatter.py        # spoken commands, punctuation, capitalization
    llm_cleanup.py      # Ollama LLM cleanup (optional)
    text_injector.py    # Cmd+V injection via Quartz
    settings.py         # data/settings.json persistence
    dictionary.py       # custom word hints for Whisper
    history.py          # transcription history
  apps/
    macos/
      menubar_dictation.py   # rumps menu bar orchestrator
      hud_overlay.py         # NSWindow live preview pill
      audio_recorder.py      # sounddevice capture
      warmup.py              # startup model preloading
    web/
      app.py                 # Flask server
      templates/ static/

config/
  config.py             # all paths (everything relative to project root)
cache/                  # auto-created — Whisper models live here
data/                   # auto-created — history, settings, runtime files
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and code style.

Quick start for contributors:

```bash
make setup
make test    # should all pass before submitting a PR
make lint
```

---

## Troubleshooting

**"No speech recognized" on every attempt**
- Check microphone permissions in System Settings
- Try a larger model: select `small` or `medium` from the Model menu

**Fn key not working**
- Use `Ctrl+Option+D` as the fallback
- Some external keyboards don't expose the Fn key to macOS — this is a hardware limitation

**Ollama cleanup not working**
- Start Ollama: `ollama serve`
- Pull the model: `ollama pull llama3.2:1b`
- Or disable it from the menu: **LLM Cleanup: OFF**

**App doesn't paste into some apps**
- Some apps (Finder, System Settings) don't support Cmd+V injection
- The transcript is copied to clipboard — press Cmd+V manually

---

## License

MIT — see [LICENSE](LICENSE).

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [OpenAI Whisper](https://github.com/openai/whisper).
