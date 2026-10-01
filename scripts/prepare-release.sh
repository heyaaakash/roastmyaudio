#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python_bin="${RMA_PYTHON:-.venv/bin/python}"
version="$(cat VERSION)"
if [ -n "$(git status --porcelain)" ]; then
  printf '%s\n' 'Release preparation requires a clean checkout. Finish reviewing and committing first.' >&2
  exit 1
fi
if [ "$(git rev-parse HEAD)" != "$(git rev-parse "v${version}^{commit}")" ]; then
  printf '%s\n' 'HEAD must be the exact version tag.' >&2
  exit 1
fi
RMA_PYTHON="$python_bin" bash scripts/verify.sh
"$python_bin" scripts/package_source.py
