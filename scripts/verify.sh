#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin="${RMA_PYTHON:-.venv/bin/python}"
"$python_bin" --version
"$python_bin" -m pip check
"$python_bin" -m ruff check src config tests scripts
"$python_bin" -m pytest tests
node --check src/apps/web/static/app.js
"$python_bin" scripts/check_project.py
"$python_bin" -m compileall -q src config
printf '%s\n' 'Local verification passed. Live microphone/native permissions require separate manual checks.'
