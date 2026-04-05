# 🔧 Installation & Setup Guide

This guide covers installing Whisper Flow on macOS with all dependencies and models stored locally within the project.

## 📋 Prerequisites

- **macOS 11+** (Big Sur or later)
- **Python 3.9+**
- **Git**
- **2GB+ free disk space** for models (more if using larger models)

Verify Python version:

```bash
python3 --version  # Should be 3.9 or higher
```

## Step 1: Clone or Extract Project

```bash
# If cloning from Git
git clone <repo-url> openai-whisper
cd openai-whisper

# Or navigate to existing project
cd /path/to/openai-whisper
```

## Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# You should see (.venv) prefix in your terminal
```

## Step 3: Install Dependencies

```bash
# Install all Python packages
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:

- **Core**: `openai-whisper`, `torch`, `torchaudio`, `flask`
- **macOS**: `rumps`, `pynput`, `sounddevice`, `pyobjc-*`
- **Optional**: `ollama` (for LLM cleanup)

### Troubleshooting Installation

**Issue**: `torch` installation fails

```bash
# Try installing without building from source
pip install torch torchaudio --no-build-isolation
```

**Issue**: `pyobjc` installation fails

```bash
# macOS-specific framework installation
xcode-select --install  # Install Xcode Command Line Tools
pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz
```

## Step 4: (Optional) Run Setup Script

For macOS menu bar integration, run:

```bash
bash scripts/setup.sh
```

This script handles:
- Additional macOS framework setup
- Permissions prompts
- Optional model pre-download

## Step 5: Pre-Download Models (Recommended)

Models download automatically on first use, but pre-downloading saves waiting time:

```bash
# Download turbo (recommended) and tiny.en (for live preview)
python3 scripts/download_models.py -m turbo tiny.en

# Or download all models (requires ~30GB)
python3 scripts/download_models.py -m all
```

Models are cached in `cache/models/` — all within the project.

## Step 6: Configure (Optional)

Edit [config/config.py](../config/config.py) to customize:

```python
# Cache locations (defaults shown)
CACHE_DIR = PROJECT_ROOT / "cache"
MODELS_CACHE_DIR = CACHE_DIR / "models"
TEMP_UPLOADS_DIR = DATA_DIR / "temp_uploads"

# Default model
DEFAULT_MODEL = "turbo"  # or "base", "small", etc.

# Ollama settings (if using LLM cleanup)
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"
```

## Running the Apps

### Web Interface

```bash
# Make sure virtual environment is active
source .venv/bin/activate

# Start web server
python3 src/apps/web/app.py

# Open http://127.0.0.1:5000 in your browser
```

The web app will:
- Auto-load models on startup
- Show available models in the dropdown
- Record and transcribe audio from the browser

### macOS Menu Bar App

```bash
# Activate virtual environment first
source .venv/bin/activate

# Start menu bar app
python3 src/apps/macos/menubar_dictation.py
```

The app will:
- Appear as `W`/`R` icon in menu bar
- Register global hotkey (`Fn` or `Ctrl+Option+D`)
- Show recording overlay while holding hotkey
- Auto-paste transcribed text into focused app

### Optional: Ollama LLM Cleanup

For smart text formatting using local AI:

```bash
# Install Ollama (if not already installed)
# Download and run from https://ollama.ai

# In a separate terminal, start Ollama server
ollama serve

# In another terminal, download model
ollama pull llama3.2:1b

# Now run the app — LLM cleanup will activate
python3 src/apps/macos/menubar_dictation.py
```

## 🗂️ File Organization After Setup

```
openai-whisper/
├── .venv/                    # Virtual environment (created)
├── cache/
│   ├── models/              # Whisper models (auto-downloaded)
│   │   ├── large-v3-turbo.pt
│   │   ├── turbo.pt
│   │   ├── tiny.en.pt
│   │   └── ...
│   └── cache/               # HuggingFace artifacts
├── data/
│   ├── temp_uploads/        # Web recordings
│   │   └── recording_*.webm
│   ├── dictionary.json      # Custom words
│   ├── history.json         # Transcription log
│   └── runtime/
│       ├── last_recording.wav
│       └── last_processed.txt
├── src/                     # Source code
├── config/
│   └── config.py            # All settings (no external paths!)
├── scripts/
│   ├── setup.sh
│   └── download_models.py
├── docs/                    # Documentation
├── requirements.txt         # Dependencies
└── README.md               # Main documentation
```

## ✅ Verification Checklist

After installation, verify everything works:

**Paths are local:**

```bash
python3 -c "from config.config import CACHE_DIR, print(f'Cache: {CACHE_DIR}')"
```

Should show: `Cache: /path/to/openai-whisper/cache`

**Models can be found:**

```bash
python3 -c "import whisper; m = whisper.load_model('tiny'); print('✅ Model loaded')"
```

**Web app starts:**

```bash
python3 src/apps/web/app.py
# Should show: Running on http://127.0.0.1:5000
```

**macOS app starts (requires Quartz permissions first time):**

```bash
python3 src/apps/macos/menubar_dictation.py
# Should show menu bar icon and "Listening for hotkey"
```

## 🔐 macOS Permissions Setup

The menu bar app requires these permissions:

1. **Microphone Access**
   - System Settings → Privacy & Security → Microphone
   - Allow Terminal or Python app

2. **Input Monitoring** (Catalina+)
   - System Settings → Privacy & Security → Input Monitoring
   - Allow Terminal or Python app
   - *Required for global hotkey detection*

3. **Accessibility** (older macOS)
   - System Settings → Privacy & Security → Accessibility
   - Allow Terminal or Python app

First time you run the app, macOS will prompt you. Grant all permissions.

## 🚀 Automation (Optional)

### macOS Launch Agent (Auto-start on Login)

Create `~/Library/LaunchAgents/com.whisper.dictation.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whisper.dictation</string>
    <key>Program</key>
    <string>/path/to/openai-whisper/.venv/bin/python3</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/openai-whisper/.venv/bin/python3</string>
        <string>/path/to/openai-whisper/src/apps/macos/menubar_dictation.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/path/to/openai-whisper</string>
</dict>
</plist>
```

Replace `/path/to/openai-whisper` with actual path. Then:

```bash
launchctl load ~/Library/LaunchAgents/com.whisper.dictation.plist
```

## 🐛 Troubleshooting

### "No module named 'whisper'"

```bash
# Virtual environment not activated
source .venv/bin/activate
pip install -r requirements.txt
```

### "No audio devices found"

```bash
# sounddevice library needs audio system
pip install --upgrade sounddevice
```

### "Quartz not available" (macOS menu bar app)

```bash
# PyObjC frameworks not installed
pip install pyobjc-core pyobjc-framework-Quartz
```

### Models still download to ~/.cache

Check `config/config.py` has these lines:

```python
os.environ['HF_HOME'] = str(HUGGINGFACE_CACHE_DIR)  # Must set this!
os.environ['XDG_CACHE_HOME'] = str(HUGGINGFACE_CACHE_DIR)
```

If still using external cache, restart Python or check your shell's `.bashrc`/`.zshrc` for conflicting `HF_HOME` exports.

### Web app won't start

```bash
# Remove old Flask cache
rm -rf /tmp/flask-cache

# Ensure port 5000 is free
lsof -i :5000

# Kill process if needed, or change port in config.py
```

## 📞 Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for technical deep dive
- Check [../docs/](../) for additional documentation
- See [../README.md](../README.md) for features and usage

---

**All done!** 🎉 You now have a fully self-contained speech-to-text system with models and data stored locally in your project directory.
