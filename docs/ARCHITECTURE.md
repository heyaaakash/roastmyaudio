# Architecture

One native menu app owns capture, inference scheduling, its loopback server, and a reusable WebKit workspace. A standalone browser client remains an optional source entry point. Canonical code is in `src/apps/web/`, `src/apps/macos/`, `src/shared/`, and `config/`; retained prototypes are excluded from packaging.

```text
Mac workspace buttons / menu / Fn or fallback
  → SessionController → one sounddevice input + bounded timer
  → saved WAV + processing history entry
  → serialized speech worker → faster-whisper
  → explicit corrections/snippets → optional cleanup/style → formatter
  → update same history entry → workspace result
  → hotkey only: main-thread target check → paste + clipboard restoration

Native menu app → owned loopback Werkzeug server → WKWebView
  → web UI and shared APIs → durable draft/settings/history/personalization
  → same-origin main-frame command/draft/copy/export bridge

Standalone browser → MediaRecorder → local POST /transcribe
  → bounded temporary upload → PyAV decode → shared processing
  → history WAV/JSON → result → temporary cleanup
```

`launcher.py` establishes desktop mode before importing configuration. Frozen resources use PyInstaller's resource root; writable data/cache remain outside the bundle. Desktop storage uses Application Support/Caches; source web uses project directories. VERSION is authoritative for UI, package, and bundle metadata.

| Path | Responsibility |
| --- | --- |
| src/apps/macos/session_controller.py | One capture lifecycle, preference/target snapshot, saved-audio retry, late-result suppression, serialized worker |
| src/apps/macos/menubar_dictation.py | Compact menu, shortcut hooks, Cocoa main-thread UI/insertion, lifecycle events |
| src/apps/macos/platform_services.py | Explicit permissions, target-safe paste, login items, content-free diagnostics |
| src/apps/macos/app_lifecycle.py | Per-store instance lock, reopen request, non-destructive known-data import |
| src/apps/macos/workspace_server.py | Owned loopback server, reserved port fallback, shutdown |
| src/apps/macos/workspace_window.py | Reusable WKWebView, guarded navigation/bridge, explicit Save Panels |
| src/apps/web/app.py | Local APIs, settings validation, bounded uploads and cleanup |
| src/apps/web/static/ | Vanilla UI, native commands or browser capture, guided setup and personalization |
| src/shared/transcriber.py | Cached model, CPU/int8 inference locks, one normalization pass |
| src/shared/history.py | Stable IDs, retained WAV, failed/interrupted recovery, atomic locked JSON |
| src/shared/workspace_state.py | Durable draft/theme/setup state across origins and launches |
| src/shared/personalization.py | Bounded explicit corrections, whole-phrase snippets, exact app styles |
| packaging/macos/ | PyInstaller recipe, entitlements, icon; no private data/model weights |
| scripts/ | Local checks, isolated smokes/captures, source and native preview packaging |

History/settings/vocabulary/workspace/personalization use file locks and atomic replacement. They are local files, not a multi-user database. Native inference has a single daemon worker; cancel/quit invalidate a session generation so late results cannot paste. Failures retain saved audio. Retry is review-only. Restart marks interrupted processing failed for recovery. Sleep requests cancel; physical sleep/wake has not been validated.

The workspace's draft is saved through a native message on input or serialized same-origin browser requests. LocalStorage supplies a recovery copy, not the authoritative store. Model preparation is explicit, with honest downloading/initializing status rather than fabricated percentages. Permissions and login registration are explicit; context/feedback default off. There is no parallel live-transcript model or background context poller.

The desktop binds loopback and does not adopt an unrelated local server. Hash navigation preserves the renderer across menu routes. Closing the window retains it; quitting clears WebKit and stops only its owned server. Preferences are refreshed on the Cocoa runloop and snapshotted per recording. A second source process requests the existing app to reopen rather than capturing independently.

Native navigation is restricted to the server origin; explicit HTTPS links open externally. WebKit media permission is denied because capture is native. Bridge payloads are bounded and must come from the same main frame. No arbitrary file path or shell execution is exposed. Separate browser processes retain their own capture lifecycle; they are not global native controllers. Screenshots/tests use labeled fictional fixtures and do not establish speech accuracy.
