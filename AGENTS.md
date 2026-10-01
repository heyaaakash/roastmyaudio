# Working on RoastMyAudio

## Canonical source and scope

Use `src/apps/web/`, `src/apps/macos/`, `src/shared/`, and `config/`. The other app directories are retained prototypes; do not silently switch entry points or copy their outdated instructions into user docs. Source-preview distribution only until the launch gates are closed. `VERSION` is authoritative; pyproject reads it dynamically.

## Verified development commands

- `make setup PYTHON=python3.12`: core/developer dependencies, `.venv` only.
- `make web`: local Flask workspace, loopback port 5000; `FLASK_PORT` can override it.
- `make setup-macos`, `make run`: native extras and combined menu app/workspace source preview.
- `make setup-cleanup`: optional llama.cpp; not needed for unit/browser tests.
- `make verify`: dependency check, Ruff, pytest, JS syntax, doc links, metadata, Python compilation.
- `make screenshots`: Playwright UI checks and six captures; start the server separately and see docs/DEVELOPMENT.md for the browser setup.
- `make package`: allowlisted source ZIP, extraction comparison, provenance and SHA-256 manifest. Refuses existing staging.
- `make prepare-release`: requires a clean checkout at the exact version tag, verifies, then packages.
- `make draft-release`: requires matching provenance, hashes, clean tag and remote tag; uploads a prerelease draft only when separately authorized.

## Product and data constraints

Keep the web UI local and same-origin. Preserve microphone release, bounded uploads/recordings, temp cleanup on both success and failure, settings validation, and file locking/atomic JSON writes. Treat transcripts, recordings, clipboard context, and local paths as sensitive. Use temporary isolated fixtures in tests. Never commit runtime audio, `data/`, model caches, tokens, or generated dist artifacts.

Do not load external fonts/analytics. Honor keyboard access, dialog focus, small screens, and reduced motion. Do not invent usage stats, performance benchmarks, paid quotas, compatibility, or feature availability. Label sample transcripts and disclose mocked tests.

Keep GitHub Actions workflows absent. Remote Actions is already disabled as checked during preparation. Preserve existing user work and public Git history; history rewrites, publication, visibility changes, tags, and remote settings need authorization appropriate to the task. Do not infer it from a guide template. Update docs/CAPABILITY_MATRIX.md and docs/VALIDATION.md from actual results.
