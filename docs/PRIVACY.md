# Data and privacy

These statements describe canonical `src/` code. Desktop defaults are `~/Library/Application Support/RoastMyAudio/` for data and `~/Library/Caches/RoastMyAudio/` for models. Standalone source web defaults are project `data/` and `cache/`. Explicit `RMA_DATA_HOME` / `RMA_CACHE_HOME` overrides apply before launch. The app bundle contains code and libraries, not user data or weights.

| Data | Processing/storage | Retention/removal |
| --- | --- | --- |
| Browser audio | Local Flask upload under temp_uploads; decoded retained WAV under recordings | Temporary upload removed on success/failure; saved WAV until Delete |
| Native audio | One sounddevice session; bounded five minutes; WAV saved before inference | Failed/interrupted inference retains audio for retry; unfinished capture discarded on cancel/quit |
| Transcript/history | history.json: original, corrected/cleaned/formatted text, app name, time, duration, model, flags | No automatic expiry; Dismiss retains; Delete removes entry and associated WAV |
| Draft/theme/setup | workspace.json; browser has a localStorage recovery copy | Clear Scratchpad to save empty; clearing site data alone does not delete the server draft |
| Vocabulary/settings | dictionary.json / settings.json | Edit in UI or remove files with app stopped |
| Personalization | personalization.json: explicit corrections, snippets, app styles | Remove in Preferences; no automatic learning |
| Failed unsaved capture | Browser tab or native memory when disk save fails | Retry while client remains open; discard/quit removes memory copy |
| Models | Cache models/huggingface/llm directories | Remove with app stopped; next use downloads again |
| Earlier runtime copies | Project data/legacy-runtime, preserved during preparation | Owner can review/delete; historical Git copies remain |

The source desktop launcher imports allowlisted project JSON and WAV recordings only into an empty desktop store, without removing originals. It does not import unrelated files or model caches. A bundle does not search for a source checkout. Back up both stores if you used both modes.

Speech inference uses faster-whisper locally. Optional cleanup uses llama.cpp locally; acceleration depends on its build. Installing dependencies and downloading models contacts package repositories and Hugging Face, which can receive ordinary download metadata. Offline operation requires cached models. The UI loads no remote fonts, analytics, or crash-reporting assets. Application configuration disables Hugging Face telemetry and ONNX Runtime model telemetry; this is not an audit of every third-party binary or service. Release checking explicitly opens GitHub in a browser.

Native shortcuts capture the foreground application's name, bundle identity, and process ID at recording start to check the destination before paste. Clipboard context is off by default and reads text only when enabled. No background clipboard polling or automatic vocabulary learning is used. The context text can become an inference prompt; history stores the app name, not that clipboard prompt.

Native paste checks the foreground identity again, temporarily sets clipboard text, sends paste, and restores prior clipboard formats if no newer clipboard change intervenes. A sent shortcut does not prove insertion into a text field. On focus change or permission failure, review/copy from the workspace. Explicit Copy replaces clipboard contents intentionally. A clipboard manager or destination app may retain what you copied/pasted.

WebKit uses native recording commands; its browser microphone requests are denied. The bridge accepts bounded, same-origin, main-frame commands/text only. Transcript/diagnostics exports use explicit native Save Panels. Diagnostics include version, OS/architecture, Python, permission flags, selected model/language, cleanup flag, and dependency versions; they omit transcripts, recordings, clipboard text, and local paths. Logs can still include setup errors and local paths; review before sharing.

Files are not encrypted by this app. Anyone with local filesystem access may read them. Keep the unauthenticated server on loopback. Stop all app/web processes and back up needed work before deleting the relevant data/cache directories. Clear browser recovery storage too. This does not delete exports, original imported project data, backups, historical Git audio, or content in other apps. Historical data remediation remains a release gate.
