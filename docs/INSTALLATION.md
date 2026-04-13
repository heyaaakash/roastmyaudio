# 🔧 Installation & Setup Guide

Complete setup instructions for **macOS menu bar app** and **web interface** (all operating systems).

## 📋 System Requirements

### For macOS Menu Bar App

- **macOS 11+** (Big Sur or later)
- **Python 3.9+**
- **Git**
- **2 GB+ free disk** (140 MB minimum for `tiny` model; prefer 2+ GB for `base` model)
- **Microphone access** (will prompt)

### For Web App (Any OS)

- **macOS, Windows, or Linux**
- **Python 3.9+**
- **Git**
- **2 GB+ free disk**
- **Modern browser** (Chrome, Firefox, Safari, Edge) with microphone access

**Check your Python version:**

```bash
python3 --version  # Should output 3.9 or higher
```

---

## Quick Start (One Command)

```bash
git clone https://github.com/open-whisperflow/open-whisperflow
cd open-whisperflow

make setup   # Creates .venv and installs all dependencies
make run     # Start macOS menu bar app
# OR
make web     # Start web UI (http://127.0.0.1:5000)
```

That's it! Skip to [Running the Apps](#running-the-apps) below.

---

## Detailed Setup (Step by Step)

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/open-whisperflow/open-whisperflow
cd open-whisperflow
```

### Step 2: Create Virtual Environment

```bash
# Create isolated Python environment
python3 -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Windows (Command Prompt):
.\.venv\Scripts\activate.bat

# You should see (.venv) prefix in your terminal prompt
```

### Step 3: Upgrade pip and Install Dependencies

```bash
# Upgrade pip (recommended)
pip install --upgrade pip

# Install all required packages
pip install -r requirements.txt
```

**What gets installed:**
- **faster-whisper** — Speech-to-text engine
- **torch, numpy** — ML backend
- **Flask** — Web server
- **sounddevice, scipy** — Audio processing
- **PyObjC, rumps** — macOS integration (macOS only)
- **pynput** — Global hotkey listening

Expect **3–10 minutes** depending on internet speed (PyTorch is large).

### Step 4: Install Dev Dependencies (Optional)

For testing, linting, and development:

```bash
pip install -r requirements-dev.txt
```

---

## Platform-Specific Setup

### macOS Setup (Menu Bar App)

#### Prerequisites

Ensure Xcode Command Line Tools are installed:

```bash
# This will prompt you if not installed
xcode-select --install
```

#### Installation

1. **Follow steps 1–4 above**

2. **Grant Accessibility Permissions**
   - Open **System Preferences → Security & Privacy → Accessibility**
   - Click the lock icon to unlock
   - Look for **"Whisper Flow"** (or Python app if not yet recognized)
   - Check the box to allow Whisper Flow to control your computer
   - Close System Preferences

   (The app will prompt for this on first use if not pre-granted.)

3. **(Optional) Pre-download models:**
   ```bash
   make download
   # Or manually:
   python3 scripts/download_models.py
   ```

4. **(Optional) Install Launch Agent (auto-start at login):**
   ```bash
   bash scripts/install_launch_agent.sh
   ```
   This creates `~/Library/LaunchAgents/com.whisperflow.plist` to auto-start the app.
   
   To remove later:
   ```bash
   rm ~/Library/LaunchAgents/com.whisperflow.plist
   ```

#### Verify Installation

```bash
make run
```

You should see:
- Menu bar icon `W` appears in the top-right
- Live preview pill overlay when you hold `Fn`
- Text pasted into active app after release

### Windows/Linux Setup (Web App)

The web app works on any OS. macOS users can use this too.

1. **Follow steps 1–4 in [Detailed Setup](#detailed-setup-step-by-step)**

2. **No additional permissions needed** — just start the web server

3. **(Optional) Pre-download models:**
   ```bash
   python3 scripts/download_models.py
   ```

---

## Running the Apps

### macOS Menu Bar App

```bash
make run
```

Or:

```bash
source .venv/bin/activate
python3 src/apps/macos/menubar_dictation.py
```

**First use:**
- Menu bar icon (`W`) appears in top-right corner
- Hold `Fn` key (or `Ctrl+Option+D` as fallback)
- Speak your text
- Release to transcribe and paste

**Menu bar icon actions:**
- Click `W` icon: Open settings menu
- Click `Quit`: Close the app
- Icon changes to `R` while recording

### Web App (All Platforms)

```bash
make web
```

Or:

```bash
source .venv/bin/activate
python3 src/apps/web/app.py
```

Then open **http://127.0.0.1:5000** in your browser.

**Using the web app:**
1. Allow microphone access when prompted
2. Click the big blue "Record" button
3. Speak your text
4. Results appear in the text area
5. Copy or download your transcription

---

## Configuration

### Environment Variables

Override settings without editing code:

```bash
# Whisper model (tiny, base, small, medium, large)
export WHISPER_MODEL=base

# Language (en, es, fr, de, zh, ja, pt, it, ko, ru)
export WHISPER_LANGUAGE=en

# Ollama LLM server (optional)
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=llama3.2:1b
```

Or create `config/.env`:

```
WHISPER_MODEL=base
WHISPER_LANGUAGE=en
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=llama3.2:1b
```

### Settings Persistence

Settings are automatically saved in `data/settings.json` when you change them in the app menu (or web interface). 

To reset to defaults, delete `data/settings.json` and restart the app.

---

## Model Management

### Downloading Models

Models download automatically on first use, but you can pre-download to save time:

```bash
# Interactive model selection
make download

# Or directly
python3 scripts/download_models.py -m base tiny.en
```

**Available models:**

| Model | Size | Speed | Accuracy | Language Support |
|-------|------|-------|----------|----------|
| `tiny` | 40 MB | ⚡⚡⚡ | ⭐⭐ | English only |
| `tiny.en` | 40 MB | ⚡⚡⚡ | ⭐⭐ | English only |
| `base` | 140 MB | ⚡⚡ | ⭐⭐⭐ | 10 languages |
| `small` | 480 MB | ⚡ | ⭐⭐⭐⭐ | 10 languages |
| `medium` | 1.5 GB | 🐢 | ⭐⭐⭐⭐ | 10 languages |
| `large` | 3 GB | 🐢 | ⭐⭐⭐⭐⭐ | 10 languages |

**Recommended:** Start with `base`, use `tiny` for speed, `small`+ for accuracy.

### Where Models Are Stored

All models cached locally in:

```
cache/
  models/
    Systran--faster-whisper-base/
    Systran--faster-whisper-small/
    ...
```

To free up space, delete unused models:

```bash
rm -rf cache/models/Systran--faster-whisper-large/
```

---

## Optional: LLM Cleanup with Ollama

For advanced grammar fixing and filler word removal, install [Ollama](https://ollama.ai):

### Install Ollama

1. Download from https://ollama.ai
2. Run the installer and open Ollama

### Download a Language Model

```bash
ollama pull llama3.2:1b  # Fast, lightweight (~1.3 GB)
# Or other options:
ollama pull mistral       # Larger, more accurate
```

### Start Ollama Server

```bash
ollama serve
# Server runs on http://localhost:11434
```

### Enable in WhisperFlow

Set environment variables:

```bash
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=llama3.2:1b
```

Now transcriptions will be automatically cleaned before pasting (or displayed in web UI).

**WhisperFlow gracefully continues** even if Ollama isn't running — you'll just get raw transcriptions.

---

## Troubleshooting

### General

**Q: Models not downloading**

A: Models download to `cache/models/` on first use. If interrupted:
```bash
rm -rf cache/models/  # Delete and retry
make run              # Restart app
```

**Q: Permission denied error**

A: Ensure virtual environment is activated:
```bash
source .venv/bin/activate
```

**Q: Module not found: `src.shared.transcriber`**

A: Make sure you're running from the project root:
```bash
cd /path/to/open-whisperflow  # The cloned folder
make run
```

### macOS Specific

**Q: Menu bar app doesn't respond to Fn key**

A: 
1. Grant **Accessibility permissions**: System Preferences → Security & Privacy → Accessibility (check WhisperFlow)
2. Grant **Microphone access**: System Preferences → Security & Privacy → Microphone (check WhisperFlow)
3. Restart the app
4. Try fallback hotkey: `Ctrl+Option+D`

**Q: "The app can't be opened because it's not from an identified developer"**

A: This is a code-signing issue with bundled `.app` files. **Simple solution:** Run from terminal:
```bash
make run  # Terminal launch always works
```

**Q: Permission denied: 'cache/'**

A: The app needs to create the `cache/` folder. Try:
```bash
mkdir -p cache data
chmod u+w cache data
make run
```

### Web App Specific

**Q: Browser won't start recording ("Microphone not found")**

A:
1. Check browser has microphone permission (browser settings)
2. Ensure microphone is connected and working
3. Test system microphone: **System Preferences → Sound → Input**
4. Try a different browser

**Q: Can't access http://127.0.0.1:5000**

A:
1. Ensure app is still running:
   ```bash
   # In another terminal, check the process
   lsof -i :5000
   ```
2. Check firewall isn't blocking port 5000 (unlikely for localhost)
3. Try `http://localhost:5000` instead

**Q: Poor accuracy on web app**

A: Accuracy depends on audio quality and microphone:
1. Use a quality microphone (built-in mics often add noise)
2. Speak slowly and clearly
3. Try a higher-accuracy model (see table above)
4. Use Ollama for grammar cleanup: [Optional: LLM Cleanup](#optional-llm-cleanup-with-ollama)

---

## Performance Tips

1. **Use `tiny` or `base` for responsiveness** (large models slow everything down)
2. **Disable LLM cleanup if not needed** (Ollama adds 1–3 seconds per transcription)
3. **Have 4+ GB RAM available** (close other apps if needed)
4. **Use a wired microphone** (or high-quality Bluetooth) for better input quality

---

## Getting Help

Still stuck?
- Check [README.md troubleshooting](../README.md#troubleshooting)
- Open a [GitHub Issue](https://github.com/open-whisperflow/open-whisperflow/issues)
- See [CONTRIBUTING.md](../CONTRIBUTING.md#reporting-issues) for bug report guidelines


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
