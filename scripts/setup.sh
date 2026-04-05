#!/bin/bash

# Setup script for Whisper Flow on macOS
# This script ensures all dependencies and local paths are properly configured

set -e  # Exit on error

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"

echo "🔧 Whisper Flow - macOS Setup"
echo "================================"
echo ""

# Check Python version
echo "1️⃣  Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Found Python $python_version"

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi

# Check for Xcode Command Line Tools
echo ""
echo "2️⃣  Checking Xcode Command Line Tools..."
if ! command -v xcode-select &> /dev/null; then
    echo "❌ Xcode Command Line Tools not installed"
    echo "   Run: xcode-select --install"
    exit 1
fi

if [ -z "$(xcode-select -p 2>/dev/null)" ]; then
    echo "⚠️  Installing Xcode Command Line Tools..."
    xcode-select --install
fi
echo "   ✅ Xcode tools available"

# Create virtual environment if needed
echo ""
echo "3️⃣  Setting up Python virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    echo "   Creating .venv..."
    python3 -m venv "$VENV_PATH"
else
    echo "   .venv already exists"
fi
echo "   ✅ Virtual environment ready"

# Activate virtual environment
echo ""
echo "4️⃣  Activating virtual environment..."
source "$VENV_PATH/bin/activate"
echo "   ✅ Virtual environment activated"

# Upgrade pip
echo ""
echo "5️⃣  Upgrading pip..."
pip install --upgrade pip --quiet
echo "   ✅ pip upgraded"

# Install dependencies
echo ""
echo "6️⃣  Installing Python dependencies..."
echo "   This may take a few minutes..."
pip install -r "$PROJECT_ROOT/requirements.txt"
echo "   ✅ Dependencies installed"

# Create necessary directories
echo ""
echo "7️⃣  Creating project directories..."
mkdir -p "$PROJECT_ROOT/cache/models"
mkdir -p "$PROJECT_ROOT/cache/cache"
mkdir -p "$PROJECT_ROOT/data/temp_uploads"
mkdir -p "$PROJECT_ROOT/data/runtime"
echo "   ✅ Directories created"

# macOS permissions notice
echo ""
echo "8️⃣  macOS Permissions Setup"
echo "   The app needs these permissions:"
echo "   - Microphone access"
echo "   - Input monitoring (global hotkey)"
echo ""
echo "   These will be requested when you first run the app."
echo "   Grant them in: System Settings → Privacy & Security"
echo ""

# Optional: Pre-download models
echo ""
echo "9️⃣  Optional: Pre-download models?"
echo "   Models auto-download on first use, but pre-downloading saves time."
read -p "   Download turbo and tiny.en now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   Downloading models (this may take 5-10 minutes)..."
    python3 "$PROJECT_ROOT/scripts/download_models.py" -m turbo tiny.en
fi

# Verify setup
echo ""
echo "🔟 Verifying setup..."
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT/config')
from config import CACHE_DIR, MODELS_CACHE_DIR, TEMP_UPLOADS_DIR
print(f'   Cache directory:    {CACHE_DIR}')
print(f'   Models directory:   {MODELS_CACHE_DIR}')
print(f'   Uploads directory:  {TEMP_UPLOADS_DIR}')
print('   ✅ All paths configured correctly')
" || {
    echo "❌ Setup verification failed"
    exit 1
}

echo ""
echo "================================"
echo "✅ Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Activate virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2. Run web app:"
echo "   python3 src/apps/web/app.py"
echo "   Then open http://127.0.0.1:5000"
echo ""
echo "3. Or run menu bar app:"
echo "   python3 src/apps/macos/menubar_dictation.py"
echo ""
echo "4. For LLM cleanup (optional):"
echo "   Install Ollama from https://ollama.ai"
echo "   Then run: ollama serve"
echo ""
echo "For more help, see:"
echo "   docs/INSTALLATION.md"
echo "   docs/ARCHITECTURE.md"
echo ""
