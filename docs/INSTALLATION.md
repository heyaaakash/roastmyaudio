# Setup and first use

This is an unpublished source preview with a local ad-hoc Mac bundle. Developer ID signing, notarization, and clean installation are still open; do not treat the preview ZIP as a public installer.

## Unified Mac app

Use Python 3.12 and an interactive macOS desktop session for source development. Only the documented Apple Silicon developer environment has been checked; no minimum OS or performance guarantee is established.

```sh
git clone https://github.com/heyaaakash/roastmyaudio.git
cd roastmyaudio
make setup-macos PYTHON=python3.12
make run
```

The menu app starts its loopback server and opens first-run setup in a native WebKit window. You do not need a separate web process. Allow Microphone, prepare the speech model, then try a fictional sentence and review the result. Initial model downloads need internet and disk space; cached inference runs locally.

Microphone permission is required for recording. Input Monitoring enables global shortcuts; Accessibility enables paste into other apps. They are optional for recording inside the workspace. Permissions are requested by explicit setup actions. Source Python runs may require granting permission to the launching process; the bundled app has its own identity. Review permissions in System Settings → Privacy & Security. Changing a bundle or signing identity can require permission approval again.

Choose **Open Workspace…**, **Recent Thoughts…**, or **Preferences…** from the menu. The sidebar contains Dictionary and Scratchpad. Workspace buttons, menu actions, and shortcuts use one native controller and selected microphone. Defaults are Fn hold-to-talk, with Ctrl+Option+D fallback; tap-to-toggle is available in Preferences. The menu can pause shortcuts. External keyboards may not expose Fn. Use a normal text editor with fictional material to test paste before relying on it.

Preferences also contain input selection, spoken commands, optional sound/haptics, and context awareness. Context and feedback default off for new settings. Existing saved choices are retained. Launch at login is an explicit control available in the bundled app; registration is not part of automated testing.

Closing the workspace finishes an active session and keeps the menu app available. Saved drafts survive renderer reload, app restart, and loopback port changes. Quitting discards unfinished capture, suppresses late paste, and stops only the owned server. Saved recordings remain. Interrupted processing appears in Recent Thoughts; open recording details to retry retained audio. Cancel does not delete already saved history.

Mac data lives in `~/Library/Application Support/RoastMyAudio/`; models in `~/Library/Caches/RoastMyAudio/`. The source launcher copies known project data once into an empty desktop store, retaining the originals. Malformed JSON prevents that import. Models are not copied. Bundled launch does not discover a source checkout. `RMA_DATA_HOME` and `RMA_CACHE_HOME` can select explicit stores before launch; use isolated directories for tests.

## Build the local Mac preview

```sh
make setup-bundle
make build-macos
```

Outputs: `dist/macos/RoastMyAudio.app`, an architecture/version-named preview ZIP, and `BUILD_INFO.json` with source provenance and SHA-256. The app includes its Python runtime and web assets; it excludes recordings and model weights. The local build uses ad-hoc signing. No Developer ID certificate, notarization, DMG installer, automatic updater, or public upload is provided. `RMA_CODESIGN_IDENTITY` selects an already configured signing identity; this alone does not notarize the app.

The checked arm64 bundle loads real Cocoa/WebKit and performs real base-model inference on generated English audio. Capture, permissions, clipboard, and Save Panel interactions in the UI smoke use fictional adapters. Human permission approval, microphone audio, paste, login registration, clean installation, sleep/wake, and Intel builds remain unverified. See [validation](VALIDATION.md).

## Standalone local web workspace

```sh
make setup PYTHON=python3.12
make web
```

Open http://127.0.0.1:5000. Start dictating, allow the browser microphone, speak, finish, and copy or move the result to Scratchpad. Option/Alt+D starts/stops; `/` focuses search; `?` opens help. Browser capture uses MediaRecorder and a secure localhost context. It does not control the native session or paste into unrelated apps.

Recordings stop after five minutes; uploads are limited to 25 MB. Failed uploads can be retried while the tab remains open. Closing/reloading loses pending tab audio. Temporary uploads are removed after processing; successful recordings remain as WAV until deleted. Draft/theme are saved by the local server with a browser recovery copy. Source web storage defaults to project `data/` and `cache/`; share an explicit data directory only if you intend to share private history.

If port 5000 is occupied, use `FLASK_PORT=5057 make web`. The desktop automatically reserves another loopback port without taking over an existing server.

The manifest declares Python 3.10+; only 3.12 was checked. Windows/Linux and browsers beyond Chromium are unverified source paths. Without Make, create `.venv`, install `requirements.txt` and `requirements-dev.txt`, then run `src/apps/web/app.py` using that environment's Python.

## Optional local cleanup and personalization

`make setup-cleanup` adds llama-cpp-python; no Ollama is required. Enable Local AI cleanup in Preferences and choose a model. GGUF weights download on demand. Real GGUF inference remains unverified here. If unavailable, the transcript and rule-based formatting remain usable. “Keep my words” skips AI and spoken command interpretation for that recording.

Dictionary adds recognition hints. Preferences lets you define exact corrections, whole-phrase snippets, and styles for exact application names. Snippets replace the complete recognized phrase; they do not expand incidental text inside a sentence. Verbatim skips AI; other styles require cleanup to be enabled. Nothing is learned automatically.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Microphone declined | Review OS permission and browser permission if using the standalone browser; return to setup |
| Input disconnected | Reconnect or select System Default in Preferences; try a new session |
| Model preparation fails | Check connection and disk space; prepare again; initial download can take time |
| Transcription fails | Retry retained audio; change model/language if appropriate; check disk space |
| Fn unavailable | Try Ctrl+Option+D and review Input Monitoring |
| Paste unavailable or focus changed | Open the workspace, review the text, and copy explicitly; check Accessibility |
| Port occupied | Desktop uses a free port; standalone web needs FLASK_PORT |
| Login control unavailable | It requires a bundled app and supported macOS service; review Login Items |
| Need help diagnosing | Export diagnostics from Preferences; review the file before sharing |
| Cleanup dependency fails | Keep cleanup off, or install required compiler tooling |

Keep the unauthenticated server on loopback. [Privacy](PRIVACY.md) · [Capabilities](CAPABILITY_MATRIX.md)
