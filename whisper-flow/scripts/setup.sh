#!/bin/bash

# RoastMyAudio - Setup Script
# Works on macOS (tested on Apple Silicon)

set -e

echo "🎙️ Setting up RoastMyAudio..."

# 1. Check for Prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found. Please install it first: https://brew.sh/"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found."
    exit 1
fi

# --- Python Selection Logic ---
PYTHON_CMD="python3"

# Check if current Python 3 is 3.14+ (which has known build issues with AI libs)
CURRENT_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
if [[ $(echo "$CURRENT_VER >= 3.14" | bc -l 2>/dev/null || echo "1") -eq 1 ]]; then
    echo "⚠️  System Python ($CURRENT_VER) is too new for some libraries (like PyAV)."
    if command -v python3.12 &> /dev/null; then
        echo "✅ Found Python 3.12 at $(which python3.12), switching to it for compatibility."
        PYTHON_CMD="python3.12"
    elif command -v python3.11 &> /dev/null; then
        echo "✅ Found Python 3.11, switching to it."
        PYTHON_CMD="python3.11"
    else
        echo "❌ No compatible Python version (3.12 or 3.11) found. Installation will likely fail on 3.14+."
        echo "💡 Install Python 3.12: 'brew install python@3.12'"
        # Don't exit yet, let it try if the user knows what they are doing, but it likely fails.
    fi
fi

# 2. Install FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 Installing FFmpeg..."
    brew install ffmpeg
else
    echo "✅ FFmpeg already installed."
fi

# 3. Create Virtual Environment
echo "🐍 Creating virtual environment with $PYTHON_CMD..."
rm -rf .venv  # Remove old venv if it was failed/wrong version
$PYTHON_CMD -m venv .venv
source .venv/bin/activate

# 4. Install Dependencies
echo "📥 Installing Python dependencies (this may take a few minutes)..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Initialization
echo "📂 Initializing runtime directory..."
mkdir -p src/macos_app/runtime
mkdir -p src/web_ui/temp_uploads

echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "1. Activate venv: source .venv/bin/activate"
echo "2. Run Menu Bar App (Menubar + Fn Key): python -m src.macos_app.menubar_dictation"
echo "3. Run Web App (Windowed + Browser Interface): python -m src.macos_app.main"
echo "4. Run Web UI (Flask-only Dev Server): python -m src.web_ui.app"
echo ""
echo "Happy dictating! 🎙️"
