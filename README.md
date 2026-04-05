# 🎙️ Whisper Flow - Self-Contained Speech Recognition

A professional macOS dictation tool and web interface powered by **OpenAI Whisper**, featuring real-time transcription, LLM-based text cleanup, and seamless macOS integration—with all dependencies and models stored locally within the project.

## ✨ Features

- **🎯 Push-to-Talk (PTT)**: Hold `Fn` or `Ctrl+Option+D` to dictate and release to paste directly into any app
- **📝 Real-time Preview**: See what you're saying as you speak with low-latency overlays
- **🧠 LLM Cleanup**: Automatically formats transcripts using local Ollama (hybrid AI approach)
- **📋 Smart Formatting**: Rule-based post-conversion for structured lists, punctuation, and capitalization  
- **🌐 Web UI**: Clean, responsive web interface for uploading audio files and transcribing
- **🎛️ Model Support**: All Whisper models from `tiny` to `large-v3-turbo`
- **🍎 macOS Native**: Deep integration with system windows, shortcuts, and input monitoring

## 📦 What's New in This Restructure

✅ **Fully Self-Contained**: All cache, models, and data stored in `cache/` directory within the project
✅ **Relative Paths Only**: No hardcoded user paths — works on any machine
✅ **Unified Project Structure**: Single `src/` folder with organized submodules
✅ **Configuration Management**: `config.py` centralizes all settings
✅ **Clean Documentation**: Architecture and setup guides included
✅ **Easy Installation**: Simple setup.sh script for dependencies

## 🗂️ Project Structure

```
openai-whisper/
├── src/
│   ├── apps/
│   │   ├── macos/           # macOS Menu Bar Application
│   │   │   ├── menubar_dictation.py
│   │   │   ├── main.py
│   │   │   └── ...
│   │   └── web/             # Web-based interface (Flask)
│   │       ├── app.py
│   │       ├── templates/
│   │       ├── static/
│   │       └── warmup.py
│   └── shared/              # Shared utilities
│       ├── dictionary.py     # Custom word dictionary
│       ├── history.py        # Transcription history
│       ├── llm_cleanup.py    # Ollama LLM integration
│       └── text_injector.py  # macOS text injection
├── cache/
│   ├── models/               # Whisper model cache
│   └── cache/                # HuggingFace cache
├── data/
│   ├── temp_uploads/         # Web temporary uploads
│   ├── dictionary.json       # Custom word dictionary
│   ├── history.json          # Transcription history
│   └── runtime/              # Runtime artifacts
├── config/
│   └── config.py             # Centralized configuration
├── scripts/
│   ├── setup.sh              # Installation script
│   └── download_models.py    # Pre-download models
├── docs/
│   ├── README.md             # This file
│   ├── INSTALLATION.md       # Setup instructions
│   └── ARCHITECTURE.md       # Technical architecture
├── requirements.txt          # Python dependencies
└── .venv/                    # Python virtual environment
```

## 🚀 Quick Start

### 1. **Clone & Install**

```bash
cd openai-whisper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For macOS menu bar app, also run:

```bash
bash scripts/setup.sh
```

### 2. **Download Models** (Optional, but recommended)

Models download automatically on first use. To pre-download:

```bash
python3 scripts/download_models.py -m turbo tiny.en
```

Models are cached in `cache/models/` — all within the project!

### 3. **Run Web UI**

```bash
python3 src/apps/web/app.py
```

Open http://127.0.0.1:5000 in your browser.

### 4. **Run macOS Menu Bar App**

```bash
python3 src/apps/macos/menubar_dictation.py
```

A `W`/`R` icon appears in your menu bar. Hold `Fn` to dictate.

## 🔧 Configuration

All settings are centralized in [config/config.py](config/config.py). Key paths:

| Setting | Value | Notes |
|---------|-------|-------|
| **Cache Root** | `cache/` | All models stored here |
| **Models Cache** | `cache/models/` | Whisper models |
| **HuggingFace Cache** | `cache/cache/` | Model artifacts |
| **Temp Uploads** | `data/temp_uploads/` | Web upload buffer |
| **History** | `data/history.json` | Transcription log |
| **Dictionary** | `data/dictionary.json` | Custom words |

### Environment Variables

Override defaults with environment variables:

```bash
# Use a different model by default
export WHISPER_MODEL=base

# Enable Ollama LLM cleanup
export OLLAMA_URL=http://localhost:11434/api/generate

# Change cache location (if needed)
export HF_HOME=/path/to/custom/cache
```

## 📚 Documentation

- **[INSTALLATION.md](docs/INSTALLATION.md)** — Detailed setup for macOS, web, dependencies
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Technical design, module descriptions, flow diagrams

## 🛠️ Dependencies

### Core

- **whisper** — OpenAI speech-to-text
- **torch**, **torchaudio** — ML inference
- **flask** — Web server
- **requests** — HTTP client

### macOS-Specific

- **rumps** — Menu bar app
- **pynput** — Global keyboard events
- **sounddevice** — Audio capture
- **PyObjC** — macOS integration

### Optional

- **ollama** — Local LLM cleanup (requires running Ollama server)

All dependencies are in [requirements.txt](requirements.txt).

## 🎯 Usage Examples

### Web Transcription

1. Open http://127.0.0.1:5000
2. Click **Start Recording**
3. Speak into your microphone
4. Click **Stop Recording**
5. View formatted transcript or toggle **Raw** to see original

### macOS Dictation

1. **Hold** `Fn` (or `Ctrl+Option+D` if Fn unavailable)
2. **Speak** your text
3. **Release** key
4. Text auto-pastes into the frontmost app

Menu options:
- **Copy Last Processed** — Copy last transcript to clipboard
- **Paste Last Processed** — Paste last transcript
- **Test Overlay** — Preview the HUD display

## 🔐 Privacy & Data

✅ **All local**: Models, cache, and history stored in `cache/` and `data/` directories
✅ **No external APIs**: Except optional Ollama (runs locally)
✅ **No telemetry**: No tracking or analytics
✅ **Full control**: You own all transcription data

## 🐛 Troubleshooting

### Models Not Found

```bash
# Pre-download models
python3 scripts/download_models.py -m turbo
```

Models are cached in `cache/models/` automatically on first run.

### Ollama LLM Not Responding

Ensure Ollama is running:

```bash
ollama serve
```

If not available, app gracefully falls back to raw transcription.

### macOS Permission Errors

The app needs microphone and input monitoring permissions:

1. Open **System Preferences** > **Security & Privacy**
2. Grant microphone access to Terminal/Python
3. Enable "Input Monitoring" for Terminal/Python (Catalina+)

### Paths Still External?

Check `config/config.py` — all environment variables are set there to use local `cache/` and `data/` directories. If needed, update `HF_HOME` and other path settings.

## 📖 Development

### Running in Development Mode

```bash
# Web app with hot reload
python3 src/apps/web/app.py

# macOS app with debug output
python3 src/apps/macos/menubar_dictation.py
```

### Adding Custom Sources

Edit [src/shared/dictionary.py](src/shared/dictionary.py) to add domain-specific terminology.

## 🔗 Links

- [OpenAI Whisper](https://github.com/openai/whisper)
- [Faster Whisper](https://github.com/SYSTRAN/faster-whisper)
- [Ollama](https://ollama.ai) — Local LLM engine
- [PyObjC](https://pyobjc.readthedocs.io/) — macOS integration

## 📝 License

This project uses OpenAI Whisper (MIT License). See [LICENSE](../archive/whisper-main/LICENSE) for details.

## 💬 Support

Encountering issues? Check:
1. [docs/INSTALLATION.md](docs/INSTALLATION.md) for setup help
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical details
3. [Troubleshooting](#-troubleshooting) section above
