# UI captures

These PNGs show the actual canonical web UI rendered in Chromium using isolated, fictional API fixtures. `workspace-sample`, `workspace-dark`, and `workspace-mobile` also show the explicitly labeled sample workspace. They do not prove live transcription, AI cleanup, or a native installation. Scratchpad text is fictional.

Start the local web app, then run `make screenshots` with Playwright installed as described in [development](../docs/DEVELOPMENT.md). The script uses a fresh browser context, reduced motion for stable captures, and mocks all data APIs. It verifies desktop/mobile overflow and interactive states before reporting completion. No real user data is loaded into captures.

Captured viewports: 1440 × 1080 desktop; 390 × 844 mobile. PNGs use full-page capture, so height can exceed viewport. Review crop, contrast, overflow, and text after every visual change. `workspace-empty.png`, `workspace-sample.png`, `workspace-dark.png`, `workspace-mobile.png`, `scratchpad.png`, and `settings.png` are the expected outputs.
