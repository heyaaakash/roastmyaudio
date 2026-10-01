# Validation — 0.2.0 local preview

Recorded 2026-10-01, Asia/Kolkata. Base commit: `319839352932371cf786634304859a8c79c885fa`; tested changes are uncommitted. No new tag, Developer ID signature, notarization, clean installation, draft upload, or publication is implied.

Environment: macOS 27.0.1 (26A434), arm64; Python 3.12.13; Google Chrome 152.0.7977.77. Checks use the existing developer checkout/environment and fresh browser/temp-data contexts, not a clean end-user OS.

| Check | Method | Result and limits |
| --- | --- | --- |
| Local verification | make verify | 144 tests, no failures/skips; dependency consistency, Ruff, JS syntax, local doc links, metadata and Python compilation pass. Heavy inference/native endpoints mocked in unit tests |
| Single recording lifecycle | tests/test_unified_desktop.py | One input across sources, duplicate start/stop prevention, one history entry, failed retry updates same ID, no retry auto-paste, cancel/quit suppression, disconnected input cleanup, preference snapshots, practice isolation |
| Durable data/restart | Same suite | Draft/theme across ports and new clients, bounded settings, non-destructive import, malformed import avoids partial JSON, instance lock/reopen request, interrupted saved audio recovery |
| Target/clipboard safety | Same suite | Mocked target change blocks paste; all clipboard formats restored; failed clipboard write restores; a newer copy is preserved. No real paste/clipboard read |
| Shared storage | tests/test_storage.py | 30 concurrent thread writers retain entries; stable legacy IDs; local filelock/atomic implementation. Multi-process stress not independently tested |
| Upload/data path | tests/test_web_workspace.py | Real synthetic WAV/PyAV decode with inference mocked; playback/deletion, failure/silence temp cleanup, validation, host/origin and bounds |
| Web browser regression | scripts/screenshots.cjs | Pass: desktop/mobile overflow, sample/search/saved, vocabulary, preferences, draft reload, theme, keyboard/dialog focus, synthetic capture, failed upload retry, denied microphone; no page errors or remote UI assets; APIs/model responses are fictional fixtures |
| Desktop UI regression | scripts/check_desktop_ui.cjs | Pass: mocked native bridge, permission/practice states, native-only capture (browser getUserMedia forbidden), one session, input/shortcut settings, personalization, 740px layout; no JS errors |
| Visual inspection | Eight screenshots | Six web screens plus two desktop UI fixture screens reviewed; actual HTML/CSS, fictional data/native responses. Desktop fixture captures are Chromium renders, not proof of real OS permissions |
| Native packaged UI | app executable --smoke | Real Cocoa menu/HUD and WebKit load; setup/practice through one controller; menu stop; durable draft bridge/reload/reopen; shared preferences; reopen/sleep callbacks; occupied-port fallback; owned shutdown. Capture/inference, permissions, login, clipboard/Save Panel endpoints mocked; global hooks disabled; no human microphone/paste or physical sleep/wake |
| Actual speech pipeline | generated phrase + scripts/smoke_transcription.py | Real base download, decode, CPU/int8 inference, WAV playback/delete/temp cleanup passed in earlier source run; one synthetic English phrase |
| Actual packaged native inference | app executable --model-smoke with generated AIFF and explicit cached model | Recognized all seven words of “A small idea can become something useful.”; one completed WAV/history entry in isolated data. Clean exit after frozen helper support fix. No human microphone or benchmark evidence |
| Native packaging | make build-macos | arm64 .app built with Python runtime/web assets/icon, ad-hoc signature deep/strict verification, plist lint, preview ZIP and SHA-256/provenance. Not Developer ID signed/notarized; no weights/user recordings included |
| Source packaging | make package | 102 allowlisted source files re-extracted and byte-compared; checksums and resolved dependency provenance generated. All 144 tests also pass from the extracted archive using the existing environment. Dirty review build, ineligible for release upload |
| Remote/history checks from preparation | Read-only GitHub API and git-filter-repo audit | Repo already public/main/MIT; Actions disabled; private reporting disabled. Zero common credential signature matches; historical .wav/runtime files purged via git-filter-repo; backup bundle saved |

Resolved core: faster-whisper 1.2.1, CTranslate2 4.8.2, PyAV 18.1.0, NumPy 2.5.3, SciPy 1.18.1, Flask 3.1.3, huggingface_hub 1.33.0, filelock 4.0.7, sounddevice 0.5.6. Native: rumps 0.4.0, pynput 1.8.2, PyObjC 12.2.2; build: PyInstaller 6.22.3/hooks 2026.8. pytest 9.1.1, Ruff 0.16.9. Source BUILD_INFO records all resolved distributions. Ranges are not deterministic resolution or advisory clearance.

## Failures that informed the implementation

PyAV 19 removed an argument used by faster-whisper; the bound is now <19 and real decode passed with 18.1.0. Real WebKit exposed NSNumber bridge conversion and initial history loading issues; JSON conversion and initialization fixed them. Browser checks caught preference refresh overwriting an unsaved language change; an edit guard fixed it.

Native controller model smoke initially returned no text because it injected a generic context prompt with context disabled and normalized twice. The controller now uses dictionary hints only when context is off and lets the shared transcriber normalize once; the generated phrase recognizes seven words. A packaged multiprocessing resource tracker initially re-entered the app launcher; freeze_support now diverts Python helpers and the rebuilt model smoke exits cleanly. These are actual synthetic pipeline regressions, not evidence of varied real-world recognition.

Restricted-sandbox GUI runs and one automatic approval-review usage-limit failure prevented earlier smokes. Authorized interactive retries passed; those failures do not establish product incompatibility. No permission was granted automatically.

## Open launch checks

- Real microphone/permission journey, accents, languages, silence/noise, recording devices and disconnects.
- Actual Fn/fallback/toggle behavior, foreground target apps, clipboard managers, accessibility permissions, real paste, physical sleep/wake.
- Installed launch-at-login registration/removal and upgrade/uninstall; never enabled by these tests.
- Clean install/extracted-source dependency setup, Intel and other OS/browser versions; Safari/Firefox/Edge and physical mobile devices.
- Real optional GGUF inference, semantic quality, Metal/CPU behavior. The current preview bundle does not include the optional llama.cpp extra by default.
- Manual screen reader/contrast audit; no formal WCAG or benchmark claim.
- Full binary/dependency/model rights/advisory inventory, Developer ID signing, notarization, Gatekeeper and installer journey.
- A working private security reporting route (historical audio purged from git history; backup bundle saved).
- Clean reviewed release commit/tag, separately authorized draft/upload, download inspection and publication.

The added clipboard tests initially passed alone but failed in the full suite due to a prior module mock being removed from sys.modules. Explicit module isolation fixed their order dependency; the full and extracted-source runs both pass 144 tests.

Mac ZIP content/CRC/SHA-256 and source staged hashes passed inspection; no runtime audio, data, caches or model weights are packaged. Earlier review source packages were preserved before refreshing staging. The earlier web-only archive passed 119 tests after extraction using the existing environment; this was not a fresh dependency/OS install. Release prepare/draft guards refused dirty source before remote mutation. No remote changes or draft upload occurred.
