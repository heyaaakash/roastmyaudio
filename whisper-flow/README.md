# 🎙️ RoastMyAudio

A professional macOS dictation tool and web interface powered by **OpenAI Whisper**, **Faster-Whisper**, and **WhisperX**. It features real-time transcription, LLM-based text cleanup, and seamless macOS integration.

---

## 🚀 Features

- **Push-to-Talk (PTT)**: Hold a key (Fn or Ctrl+Option+D) to dictate and release to paste.
- **Real-time Preview**: See what you're saying as you speak with low-latency overlays.
- **LLM Cleanup**: Automatically formats transcripts using Ollama (Hybrid AI approach).
- **Smart Formatting**: Rule-based post-conversion for structured lists, punctuation, and capitalization.
- **Web UI**: A clean, responsive web interface for uploading audio files and transcribing on the fly.
- **Model Support**: Supports all Whisper models from `tiny` to `large-v3-turbo`.
- **macOS Native**: Uses `PyObjC` for deep integration with system windows, shortcuts, and input monitoring.

---

## 📂 Project Structure

```text
roastmyaudio/
├── src/
│   ├── macos_app/          # macOS Menu Bar Application
│   │   ├── main.py         # App entry point
│   │   ├── core/           # Transcription and injection logic
│   │   ├── ui/             # Overlay and menu components
│   │   └── modules/        # Dictionary, History, and LLM cleanup
│   └── web_ui/             # Web-based interface (Flask)
├── scripts/                # Setup and utility scripts
├── requirements.txt        # All dependencies
└── README.md               # You are here
```

---

## 🛠️ Installation

### 1. Prerequisites
- **Python 3.10 - 3.12** (Stable) 
  - *Note: Python 3.14+ is currently too new for some AI libraries like `torch` and `numpy`.*
- **FFmpeg**: `brew install ffmpeg`
- **Ollama** (Optional, for LLM cleanup): [Download Ollama](https://ollama.ai/)

### 2. Setup
Clone the repository and run the setup script:

```bash
git clone <your-repo-url>
cd roastmyaudio
bash scripts/setup.sh
```

### 3. Model Preparation
Download the recommended Whisper models:

```bash
python scripts/download_models.py --model turbo
```

---

## 🖥️ Usage

### macOS Application
Run the menu bar app:
```bash
python src/macos_app/main.py
```
- **Hold `Fn`** to start dictating.
- **Release `Fn`** to transcribe and inject text into the active application.

### Web Interface
Start the Flask server:
```bash
python src/web_ui/app.py
```
Visit `http://localhost:5000` in your browser.

---

## 📝 Configuration
The application stores its runtime data (dictionaries, history, etc.) in `src/macos_app/runtime/`. This directory is ignored by Git to keep your personal data private.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
