# RoastMyAudio Makefile
# All commands run inside the project-local virtual environment.
# Nothing is installed outside this directory.

PYTHON    := python3
VENV      := .venv
PIP       := $(VENV)/bin/pip
PY        := $(VENV)/bin/python
RUFF      := $(VENV)/bin/ruff
PYTEST    := $(VENV)/bin/pytest

.PHONY: help setup run web test lint download bundle clean

# ── Default target ────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  RoastMyAudio — open-source alternative to Wispr Flow"
	@echo ""
	@echo "  make setup      Create .venv and install all dependencies"
	@echo "  make run        Launch the macOS menu bar app"
	@echo "  make web        Launch the Flask web UI (http://127.0.0.1:5000)"
	@echo "  make download   Download Whisper models interactively"
	@echo "  make test       Run the pytest test suite"
	@echo "  make lint       Run ruff linter"
	@echo "  make bundle     Build a distributable RoastMyAudio.app (requires py2app)"
	@echo "  make clean      Remove .venv, cache, and compiled files"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────
setup: $(VENV)/bin/activate

$(VENV)/bin/activate:
	@echo "→ Creating virtual environment in $(VENV)/"
	$(PYTHON) -m venv $(VENV)
	@echo "→ Upgrading pip..."
	$(PIP) install --upgrade pip
	@echo "→ Installing runtime dependencies..."
	$(PIP) install -r requirements.txt
	@echo "→ Installing dev dependencies..."
	$(PIP) install -r requirements-dev.txt
	@echo ""
	@echo "✓ Setup complete."
	@echo "  Run 'make run' to start the menu bar app."
	@echo "  Run 'make download' to pre-download Whisper models."

# ── Run applications ──────────────────────────────────────────────────────
run: $(VENV)/bin/activate
	@echo "→ Starting RoastMyAudio menu bar app..."
	$(PY) src/apps/macos/menubar_dictation.py

web: $(VENV)/bin/activate
	@echo "→ Starting Flask web UI on http://127.0.0.1:5000 ..."
	$(PY) src/apps/web/app.py

# ── Model management ──────────────────────────────────────────────────────
download: $(VENV)/bin/activate
	$(PY) scripts/download_models.py

# ── Development tools ─────────────────────────────────────────────────────
test: $(VENV)/bin/activate
	$(PYTEST) tests/

lint: $(VENV)/bin/activate
	$(RUFF) check src/ config/ tests/

lint-fix: $(VENV)/bin/activate
	$(RUFF) check --fix src/ config/ tests/

# ── App bundle (macOS .app) ───────────────────────────────────────────────
bundle: $(VENV)/bin/activate
	@echo "→ Building RoastMyAudio.app..."
	$(PIP) install py2app
	$(PY) setup_bundle.py py2app
	@echo "✓ App built in dist/RoastMyAudio.app"

# ── Cleanup ───────────────────────────────────────────────────────────────
clean:
	@echo "→ Removing virtual environment and compiled files..."
	rm -rf $(VENV) __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Clean complete. Run 'make setup' to start fresh."
