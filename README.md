# WhisperFlow

Open-source macOS dictation tool — a fully local alternative to Wispr Flow.

Hold a key, speak, release — text appears in any app.
Nothing leaves your machine. No subscription. No cloud.

---

## How it works

```
Hold Fn  →  speak  →  release  →  text pastes into any app
```

A menu bar icon (`W`) lives in your top bar. While you hold the trigger key, a pill overlay shows a live preview of your words. On release, Whisper transcribes locally and injects the text via Cmd+V.

---

## Quickstart

```bash
git clone https://github.com/your-username/open-whisperflow
cd open-whisperflow

make setup     # creates .venv, installs deps — nothing outside this folder
make run       # launches the menu bar app
```

That's it. The first time you hold `Fn`, the model downloads to `cache/models/` (140 MB for base).

**Optional: pre-download models before first use**

```bash
make download
```

**Optional: start automatically at login**

```bash
bash scripts/install_launch_agent.sh
```

---

## Features

- **Push-to-talk** — hold `Fn` (or `Ctrl+Option+D` as fallback)
- **Live preview** — see transcription words appear in real time while speaking
- **Spoken commands** — say "new line", "period", "bullet point" and they become text
- **LLM cleanup** — optional [Ollama](https://ollama.ai) integration removes filler words and fixes grammar locally
- **10 languages** — English, Spanish, French, German, Chinese, Japanese, Portuguese, Italian, Korean, Russian
- **All models** — `tiny` (40 MB) to `large-v3` (3 GB), switchable from the menu
- **Web UI** — browser-based transcription at `http://127.0.0.1:5000` (`make web`)
- **Private by design** — no telemetry, no API calls, all data in `cache/` and `data/`

---

## Privacy story

Everything runs on your computer:

- Models cached in `cache/models/` inside this folder
- Transcription history saved in `data/history.json` inside this folder
- Settings saved in `data/settings.json` inside this folder
- No internet connection required after first model download
- No crash reporting, no analytics, no external servers

The optional Ollama LLM also runs locally (`localhost:11434`).

---

## Commands

```bash
make setup      # create .venv and install all dependencies
make run        # start macOS menu bar app
make web        # start Flask web UI (http://127.0.0.1:5000)
make download   # download Whisper models interactively
make test       # run test suite
make lint       # check code style with ruff
make clean      # remove .venv and compiled files
```

---

## Configuration

Settings persist automatically in `data/settings.json` when changed from the menu.

You can also override via environment variables:

```bash
export WHISPER_MODEL=small      # default: base
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=llama3.2:1b
```

Or copy `config/.env.example` to `config/.env` and edit it.

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
