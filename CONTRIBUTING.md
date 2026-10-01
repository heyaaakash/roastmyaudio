# Contributing

Thanks for taking the time to make this little tool better. A concrete workflow, a clear bug reproduction, or a small thoughtful improvement is a good place to start.

1. Use Python 3.12 and `make setup`; work in `src/`, not the retained prototypes.
2. Describe the user's problem and the resulting behavior.
3. Run `make verify`. For UI work, run the optional browser checks and review desktop/mobile captures.
4. Add tests for meaningful risks such as audio retention, failed requests, privacy boundaries, and state transitions. Do not add tests that only repeat trivial implementation details.
5. Include the commands you actually ran and disclose mocked/unverified integrations.

Use fictional recordings and transcripts. Redact tokens, local paths, clipboard contents, and personal audio from logs and public issues. Do not download models or access production accounts from automated tests. Aakash maintains merge and release decisions.

This project uses local verification. Do not add GitHub Actions workflows or CI badges. Keep versions in `VERSION`; update capability evidence and docs when behavior changes. Read [development instructions](docs/DEVELOPMENT.md), [privacy](docs/PRIVACY.md), and the [code of conduct](CODE_OF_CONDUCT.md). Sensitive vulnerabilities follow [SECURITY.md](SECURITY.md).
