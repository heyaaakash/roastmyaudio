# RoastMyAudio 0.2.0 — local voice workspace preview

Prepared 2026-10-01. **Unpublished working changes; source distribution only while launch gates remain open.** This is not a signed installer or a hosted service.

The web workspace now focuses on dictation, recent thoughts, vocabulary, drafts, and preferences. It adds light/dark appearance, mobile layouts, reduced-motion support, audio-reactive animation, keyboard shortcuts, accessible dialogs, clear errors, retryable browser uploads, labeled samples, and accurate activity counts. Placeholder meeting tools and paid-plan UI are removed.

The upload path now decodes browser audio into the 16 kHz array expected by the engine, retains successful audio as WAV, and cleans temporary uploads. Language/model/cleanup settings are honored. Local storage uses file locks and atomic JSON replacement. PyAV is capped below 19 to avoid its incompatible API change. Optional cleanup download calls use the current Hugging Face signature.

The macOS menu app now owns the workspace server and opens the web interface in a reusable native WebKit window. Menu routes share history/dictionary/preferences, a native clipboard/export bridge, and lifecycle handling with a free-port fallback. The browser remains optional. The Mac app now has one recording controller across workspace/menu/shortcuts, guided setup, durable Application Support data, explicit personalization and login controls, diagnostics, and saved-audio recovery. A local arm64 ad-hoc bundle is buildable and smoke-tested; no Developer ID signed/notarized installer exists.

Requirements: Python 3.12 recommended; browser microphone support on localhost; network for initial dependencies/models. Source setup uses `make setup` then `make web`. Optional native macOS/LLM extras have separate commands. No binary signing or notarization claim is made.

See [validation](https://github.com/heyaaakash/roastmyaudio/blob/main/docs/VALIDATION.md), [capabilities](https://github.com/heyaaakash/roastmyaudio/blob/main/docs/CAPABILITY_MATRIX.md), [setup](https://github.com/heyaaakash/roastmyaudio/blob/main/docs/INSTALLATION.md), and [privacy](https://github.com/heyaaakash/roastmyaudio/blob/main/docs/PRIVACY.md). Human microphone accuracy, native permissions, other browsers/OSes, and optional AI inference remain unverified. Earlier Git history includes runtime audio; private security reporting is currently disabled. These must be resolved before a new public release.

To roll back a source checkout, stop apps, back up the desktop Application Support store and project `data/`, and return to a previously reviewed commit. Retained newer data is not guaranteed to be readable by older prototypes. Do not replace existing tags/artifacts silently. Report bugs with synthetic examples at https://github.com/heyaaakash/roastmyaudio/issues.
