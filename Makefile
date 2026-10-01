# Local verification only. VERSION is authoritative. Override PYTHON as needed.
PYTHON ?= python3.12
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
.DEFAULT_GOAL := help
.PHONY: help setup setup-macos setup-cleanup web run download test lint verify screenshots package prepare-release draft-release clean
help:
	@echo "RoastMyAudio · your voice, in words"
	@echo "setup / setup-macos / setup-cleanup · install core / native extras / optional AI"
	@echo "web / run / download · web workspace / macOS app / pre-download models"
	@echo "test / lint / verify / screenshots · local checks and browser captures"
	@echo "setup-bundle / build-macos / smoke-macos · local native preview"
	@echo "package / prepare-release / draft-release · source-only release tooling"
setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt -r requirements-dev.txt
setup-macos: setup
	$(PIP) install -e '.[macos]'
setup-cleanup:
	$(PIP) install -e '.[cleanup]'
web:
	$(PY) src/apps/web/app.py
run:
	$(PY) src/apps/macos/launcher.py
download:
	$(PY) scripts/download_models.py
test:
	$(PY) -m pytest tests
lint:
	$(PY) -m ruff check src config tests scripts
verify:
	RMA_PYTHON=$(PY) bash scripts/verify.sh
screenshots:
	node scripts/screenshots.cjs
package:
	$(PY) scripts/package_source.py
prepare-release:
	RMA_PYTHON=$(PY) bash scripts/prepare-release.sh
draft-release:
	$(PY) scripts/draft_release.py
clean:
	$(PY) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', 'build', 'roastmyaudio.egg-info']]"

.PHONY: setup-bundle build-macos smoke-macos
setup-bundle:
	$(PIP) install -e '.[macos,bundle]'
build-macos:
	$(PY) scripts/build_macos.py
smoke-macos:
	$(PY) scripts/smoke_macos_workspace.py
