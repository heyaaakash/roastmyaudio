# RoastMyAudio launch preparation

Applied guide: [Public Project Launch Guide v3](LAUNCH_GUIDE.md). Record date: 2026-10-01, Asia/Kolkata. Unchecked items remain open; no public-release completion is claimed.

## Project card

| Field | This project |
| --- | --- |
| Product / audience / first outcome | RoastMyAudio; local dictation for people who think out loud; record a sentence and copy it |
| Owner / support | Aakash / GitHub heyaaakash; repository issues; private vulnerability reporting is disabled and must be established |
| Source / Git root / destination | `/Users/isd0605/Documents/Github/roastmyaudio`; same path; no migration requested |
| Remote / branch | https://github.com/heyaaakash/roastmyaudio.git; main |
| Structure | Unified native shell/workspace with shared engine and optional browser client; retained prototypes excluded from packaging |
| Visibility | Already public, confirmed through GitHub API; no visibility change performed |
| Presentation reference | Wispr Flow quality/interaction inspiration; own code/art/icon, no parity or affiliation claim |
| Platforms | Chromium/macOS arm64 checked with fixtures; other browsers/OSes and native usage unverified |
| Release scope / channels | Source-only distribution preparation; local ad-hoc native preview built; no public binary/store/site deployment |
| Automation | Local verify/screenshots/package/prepare/draft scripts; no workflows; remote Actions disabled (API check) |
| Identity / version | roastmyaudio; VERSION 0.2.0; waveform SVG/icns; local bundle com.heyaaakash.roastmyaudio |
| Signing | Source archive signing N/A; local arm64 bundle ad hoc, not Developer ID signed/notarized |
| License / rights | Existing MIT retained; full-history rights and dependency redistribution review open |
| Data | Desktop Application Support/Caches, source web data/cache, shared durable draft, explicit personalization/context; model download services |
| Claims / evidence | CAPABILITY_MATRIX.md and VALIDATION.md; fictional screenshots disclosed |
| Authorization | Local repo transformation and preparation requested in this chat; no push/tag/draft/publish/history-rewrite/remote-settings authorization |
| Maintenance / rollback | Aakash; review before release and monthly while active; stop/back up data before source downgrade |

## Decisions

| Decision | Reason | Alternative / remaining risk | Revisit |
| --- | --- | --- | --- |
| Preserve root/history | Existing product; no move needed | Prior runtime audio remains in history | Owner reviews privacy/remediation |
| Keep canonical `src/`, label prototypes | Shared engine is the active implementation | Duplicate prototypes can confuse; root docs/archives route to src | Remove/archive with deliberate history plan |
| Source preview scope | Public gates and human install/permission journey remain open | No signed/notarized binaries | Signing/clean installation and human permission evidence exists |
| Separate optional native/AI dependencies | Core browser setup should not require macOS or compiling an LLM | Cross-platform setup still needs target testing | Platform matrix expands |
| Own visual identity | Aim for thoughtful interaction quality | Not Wispr feature/performance parity | Actual user feedback |
| PyAV <19 | Real decoding regression found removed metadata_errors API | Ranges are not a full dependency lock | faster-whisper compatibility changes |
| File locks + atomic JSON | Avoid torn writes and lost concurrent history updates | No hosted/multi-user/network-filesystem guarantee | Need transactional data model |

## Common phases

- [x] Inspect root/status/remote/history/tags/source/test/runtime inventory; clean working tree at start.
- [x] Preserve user work/history; no move, history rewrite, tag, commit, push, upload, or publish performed.
- [x] Core workflow, audience, first-use path, unsupported placeholders, and scope documented.
- [x] Implement focused web UI, error/retry/permission states, shared preferences, retained audio, real stats.
- [x] Keep existing MIT, own SVG/CSS artwork, system fonts, attribution and privacy docs.
- [x] Relocate earlier runtime artifacts to ignored data/legacy-runtime; no private audio in package inputs.
- [x] Pattern-scan current release inputs and 14 reachable commits for common key signatures; zero matches. This is limited evidence, not a security audit.
- [x] Review personal audio/transcripts in historical commits; owner authorized remediation; full backup bundle created (../roastmyaudio-pre-rewrite-backup.bundle); git-filter-repo purged all historical .wav and runtime text files from Git history; 0 runtime audio/text files remain in history.
- [ ] Review resolved dependency advisories and all binary/model redistribution obligations for the eventual channel.
- [x] Local instructions, contribution/security docs, support templates, version, real fixture screenshots, and local script contract provided.
- [x] No workflows; remote Actions API returned enabled=false.
- [ ] Establish private vulnerability report route. API returned enabled=false; current SECURITY.md clearly records the gap.
- [x] Run actual checks and record limits in VALIDATION.md; review desktop/mobile/dark/draft/settings captures.
- [ ] Real user microphone + native permissions and optional AI inference; Safari/Firefox/Windows/Linux if claimed.
- [ ] Clean extracted-source setup from a release tag; final commit/tag/source and release asset evidence.
- [ ] Authorization, immutable new tag, draft upload/download validation, publication, public artifact re-download and release record.

## Platform branches

- **Web app:** local-only interface and same-origin checks tested; production deployment/domain/TLS/auth/migrations N/A (no hosted release). Real browser/permission matrix remains open.
- **Desktop:** unified menu/controller/WebKit preview; arm64 bundle built and packaged UI/model smokes passed with synthetic capture and disabled hooks; Developer ID/notarization/install/upgrade/uninstall/live hotkey checks open.
- **Mobile stores, VS Code extension, Chrome extension:** N/A, not products in this repository.

## Release record

| Field | Current status |
| --- | --- |
| Version / source | 0.2.0 working changes on 319839352932371cf786634304859a8c79c885fa; not committed/tagged |
| Build / assets | Refreshed allowlisted source package extracted/byte-compared; local arm64 .app/preview ZIP with ad-hoc verification/hash/provenance; dirty builds ineligible for public release |
| Publication | No release draft, deployment, publication, or new tag |
| Public repository | Already public; GitHub API confirmed heyaaakash/roastmyaudio / main / MIT |
| Signing | Source archive N/A; native preview ad hoc, not notarized |
| Checks / limits | See VALIDATION.md and CAPABILITY_MATRIX.md |
| Final go/no-go | No-go for a new public release until rights/history/privacy-route/clean-source/authorization gates close |
