# Development

Use the repository root and Python 3.12. `make setup` installs core dependencies and developer tools into `.venv`; native macOS and cleanup dependencies are separate extras. `make web` runs the local UI. Set `FLASK_PORT` if necessary. The primary app does not use the legacy prototypes.

```sh
make setup
make test
make lint
make verify
```

Tests isolate data paths in temporary directories and mock heavyweight recognition, native APIs, and AI. The web upload regressions decode a real synthetic WAV but mock model output. They verify retention, deletion, silence handling, temporary cleanup, preference validation, and cross-origin/host boundaries.

For browser checks and captures, first start `make web` in another terminal, then install Playwright locally:

```sh
npm install --prefix .playwright playwright
.playwright/node_modules/.bin/playwright install chromium
make screenshots
```

Alternatively set `RMA_PLAYWRIGHT_DIR` to an existing Playwright node_modules folder and `RMA_BROWSER_PATH` to a compatible Chromium executable. `RMA_BASE_URL` overrides http://127.0.0.1:5000. The capture script creates a fresh browser profile, uses fictional API fixtures, verifies UI interactions and synthetic microphone states, and writes six PNGs. Review them visually. It never validates real model accuracy or modifies real history/settings/dictionary.

`requirements.txt` and pyproject define compatible ranges rather than a deterministic lock. PyAV is bounded below 19 because version 19 removed the metadata_errors argument used by faster-whisper 1.2.1. See [VALIDATION.md](VALIDATION.md) for the versions actually tested. Capture resolved dependencies for every release. Optional native/LLM packages need their own compatibility validation.

For an optional real-model smoke on macOS, generate fictional audio with `/usr/bin/say -o /tmp/rma-fictional.aiff "A small idea can become something useful."`, then run `.venv/bin/python scripts/smoke_transcription.py /tmp/rma-fictional.aiff --model base`. This downloads the model if missing and isolates saved fixture data. It checks the actual pipeline, not human accuracy.

Keep the UI accessible: semantic buttons/labels, keyboard focus, dialog dismissal, visible errors, readable contrast, small-screen overflow checks, and reduced-motion support. Avoid adding unimplemented screens, invented stats, fake accounts, or paid-plan affordances.

[Architecture](ARCHITECTURE.md) · [Release process](RELEASING.md) · [Contributor expectations](../CONTRIBUTING.md)

## Native preview and checks

```sh
make setup-macos
make run
make smoke-macos
make setup-bundle
make build-macos
```

Run GUI checks in an interactive macOS session. The native smoke uses real Cocoa/WebKit and temporary data with fictional capture/inference, mocked permission/clipboard/save/login endpoints, and disabled global hooks. It checks practice setup, one session across buttons/menu, durable draft reload/reopen, shared preferences, port fallback, and owned shutdown. It does not validate actual microphone/paste/login/permissions.

The bundle uses the same launcher and can run its embedded smoke:

```sh
dist/macos/RoastMyAudio.app/Contents/MacOS/RoastMyAudio --smoke
RMA_CACHE_HOME="$PWD/cache" dist/macos/RoastMyAudio.app/Contents/MacOS/RoastMyAudio --model-smoke /tmp/rma-fictional.aiff
```

Model smoke isolates data, uses actual recognition on caller-supplied fictional audio, and optionally reuses an explicit cache. It does not record a human microphone. `scripts/check_desktop_ui.cjs` additionally checks the native UI through an explicitly mocked browser bridge and creates two labeled captures. It verifies that the native client never calls browser getUserMedia. Use the same Playwright/environment options as the six-screen web script.

The PyInstaller preview build verifies its ad-hoc signature and plist, creates a ZIP and provenance/hash file, and includes no user data/model weights. Build on each intended architecture. Developer ID/notarization, full binary/license inventory, and clean installation remain separate release gates. Changing code requires rebuilding before claiming packaged evidence. Icon regeneration uses `scripts/macos_icon.cjs` and macOS iconutil; the source .icns is included.

Runtime data must stay ignored. Never use real transcripts, recordings, clipboard material, or paths as fixtures. Keep generated dist/build files out of commits. No GitHub Actions workflow is used.
