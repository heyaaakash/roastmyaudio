# Capability evidence — 0.2.0 preview

Evidence date: 2026-10-01, Asia/Kolkata. Uncommitted changes based on c78d894a74032b9270d533dcc12bd3b017fafccb. Source distribution remains the launch scope; local native artifacts are developer previews.

| Capability | Implementation/evidence | Practical limits |
| --- | --- | --- |
| One Mac capture session | Native controller shared by workspace/menu/Fn/fallback; unit tests and packaged Cocoa/WebKit practice smoke | Actual human shortcut/microphone permissions and hardware unverified |
| Guided setup | Explicit permission actions, model preparation, practice and review; mocked browser bridge + real WebKit synthetic practice | Permission prompts/model status are not an end-user install validation |
| Durable drafts/preferences/history | Application Support data, cache outside bundle, locked atomic JSON; cross-port/recreated-client tests and WebKit reload/reopen | No cross-device sync; disk access required; project web defaults are a separate store |
| Retry/restart recovery | Save native audio before inference; same ID retry, no retry auto-paste; interrupted status recovered | Unsaved audio lost on quit; inference failures do not guarantee recognizability |
| Target-safe paste | Foreground identity and Accessibility checks; clipboard restoration tests with mocked OS endpoints | Sent paste is not verified insertion; actual target apps/clipboard managers unverified |
| Native controls | Input selection, hold/toggle/fallback, pause/resume, opt-in feedback/context | Hardware/haptic/global event behavior unverified |
| Login item | Explicit SMAppService checkbox in bundle; unavailable for source run | No registration/removal performed or clean installed-app test |
| Vocabulary/personalization | Hints, exact corrections, whole-phrase snippets, exact-app styles; API/unit/browser tests | No learning; hints not guaranteed; non-verbatim style rewrites need optional cleanup |
| Search/save/export/playback | Browser fixture interactions, real WAV tests, native export bridge mocked | Latest 100 loaded; sample data fictional/read-only |
| Appearance/accessibility | Light/dark, reduced motion, keyboard/dialog focus, desktop/mobile/740px checks; eight reviewed captures | Emulation only; screen reader/manual contrast audit open |
| Actual speech recognition | Source upload and packaged native base-model smoke on generated seven-word phrase | One synthetic English fixture; no accuracy/performance claims |
| Optional AI cleanup | Existing local GGUF code, prompts/fallback tests | Actual llama.cpp inference unverified; excluded from default preview bundle |
| Diagnostics/release checking | Content-free diagnostic Save Panel and explicit GitHub release link | No crash telemetry or automatic update system; no real Save Panel user interaction tested |
| macOS arm64 bundle | PyInstaller runtime/assets/icon; ad-hoc deep/strict signature and plist verification; packaged UI/model smoke | Developer machine only; no Developer ID/notarization, installer, Intel or clean-install evidence |
| Standalone browser | Separate local Flask/MediaRecorder entry; Chromium fixtures on macOS | Own capture lifecycle; other browsers and Windows/Linux unverified |
| Public signed installer / hosted app / meetings / sync | Not provided | Open gates or outside scope |

Read [VALIDATION.md](VALIDATION.md) for methods, mocks, environment, and remaining gates. Implementation and screenshots are not compatibility guarantees.
