#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
make setup PYTHON="${RMA_SETUP_PYTHON:-python3.12}"
printf '%s\n' 'Core setup complete. Run make web.' 'For the native app: make setup-macos.' 'For optional local AI: make setup-cleanup.'
