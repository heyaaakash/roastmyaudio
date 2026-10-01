/* Desktop UI contract checks in Chromium; native endpoints are explicit fixtures. */
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const root = path.resolve(__dirname, "..");
const { chromium } = require(
  require.resolve("playwright", {
    paths: [
      process.env.RMA_PLAYWRIGHT_DIR ||
        path.join(root, ".playwright/node_modules"),
    ],
  }),
);
const base = process.env.RMA_BASE_URL || "http://127.0.0.1:5000";
(async () => {
  const launch = { headless: true };
  if (process.env.RMA_BROWSER_PATH)
    launch.executablePath = process.env.RMA_BROWSER_PATH;
  const browser = await chromium.launch(launch);
  try {
    const context = await browser.newContext({
      viewport: { width: 1180, height: 840 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let workspace = { draft: "", theme: "light", onboarding_complete: false };
    let library = { corrections: [], snippets: [], app_styles: [] };
    let settings = {
      model: "base",
      language: "en",
      llm_enabled: false,
      llm_model: "qwen2.5-0.5b",
      hotkey: "fn",
      dictation_mode: "push_to_talk",
      device_id: null,
      context_awareness: false,
      voice_commands: true,
      haptics_enabled: false,
    };
    await page.route("**/api/**", async (route) => {
      const request = route.request(),
        url = new URL(request.url());
      let data = {};
      if (url.pathname === "/api/history") data = { recordings: [] };
      if (url.pathname === "/api/stats")
        data = { total_words: 0, total_recordings: 0, total_minutes: 0 };
      if (url.pathname === "/api/dictionary") data = { words: [] };
      if (url.pathname === "/api/workspace") {
        if (request.method() === "POST")
          workspace = { ...workspace, ...request.postDataJSON() };
        data = workspace;
      }
      if (url.pathname === "/api/settings") {
        if (request.method() === "POST")
          settings = { ...settings, ...request.postDataJSON() };
        data =
          request.method() === "POST" ? { success: true, settings } : settings;
      }
      if (url.pathname === "/api/personalization") {
        if (request.method() === "POST") library = request.postDataJSON();
        data = library;
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(data),
      });
    });
    await page.addInitScript(() => {
      const session = {
        phase: "idle",
        message: "Ready when you are",
        text: "",
        recording_id: null,
        seconds: 0,
        level: 0,
        can_retry: false,
        error: "",
        permissions: {
          microphone: "not_requested",
          accessibility: false,
          input_monitoring: false,
        },
        login: { available: true, enabled: false },
      };
      window.fixtureCaptureStarts = 0;
      window.roastmyaudioDesktop = {
        saveDraft: async (draft) =>
          (
            await fetch("/api/workspace", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ draft }),
            })
          ).json(),
        copy: async () => {},
        exportText: async () => {},
        command: async (action, payload = {}) => {
          if (action === "devices")
            return [{ id: 7, name: "Fictional microphone" }];
          if (action === "permission")
            session.permissions[payload.kind] =
              payload.kind === "microphone" ? "granted" : true;
          if (action === "prepare") {
            session.message = "Speech model ready";
            session.model_ready = "base";
          }
          if (action === "start") {
            window.fixtureCaptureStarts++;
            Object.assign(session, {
              phase: "recording",
              text: "",
              source: "workspace",
              practice: payload.practice,
              message: "Listening",
            });
          }
          if (action === "stop")
            Object.assign(session, {
              phase: "idle",
              text: "A fictional practice thought.",
              recording_id: "fixture_native_1",
              message: "Thought captured",
            });
          if (action === "cancel")
            Object.assign(session, {
              phase: "idle",
              can_retry: false,
              error: "",
            });
          if (action === "onboarding") {
            await fetch("/api/workspace", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ onboarding_complete: true }),
            });
          }
          if (action === "login") {
            session.login.enabled = payload.enabled;
            return session.login;
          }
          setTimeout(
            () =>
              dispatchEvent(
                new CustomEvent("rma-session", { detail: session }),
              ),
            0,
          );
          return {
            ...session,
            permissions: { ...session.permissions },
            login: { ...session.login },
          };
        },
      };
      navigator.mediaDevices.getUserMedia = () => {
        throw new Error("Desktop must not capture through WebKit/browser");
      };
    });
    await page.goto(base);
    await page.locator("#setupDialog").waitFor({ state: "visible" });
    assert.equal(await page.locator("#practiceBtn").isDisabled(), true);
    await page.locator('[data-permission="microphone"]').click();
    await page.locator("#prepareModelBtn").click();
    assert.equal(await page.locator("#practiceBtn").isDisabled(), false);
    fs.mkdirSync(path.join(root, "screenshots"), { recursive: true });
    await page.screenshot({
      path: path.join(root, "screenshots/macos-setup.png"),
      fullPage: true,
    });
    await page.locator("#practiceBtn").click();
    await page.waitForFunction(
      () =>
        document.querySelector("#practiceBtn").textContent ===
        "Finish practice",
    );
    await page.locator("#practiceBtn").click();
    await page.waitForFunction(
      () => !document.querySelector("#finishSetupBtn").disabled,
    );
    await page.locator("#finishSetupBtn").click();
    assert.equal(workspace.onboarding_complete, true);
    assert.equal(await page.evaluate(() => window.fixtureCaptureStarts), 1);
    await page.locator('[data-view="settings"]').click();
    await page.locator("#deviceSetting").selectOption("7");
    await page.locator("#hotkeySetting").selectOption("ctrl_option_d");
    await page.getByRole("button", { name: "Save preferences" }).click();
    await page.waitForFunction(() =>
      document
        .querySelector("#settingsStatus")
        .textContent.startsWith("Saved."),
    );
    assert.equal(settings.device_id, 7);
    assert.equal(settings.hotkey, "ctrl_option_d");
    await page.locator("#libraryTrigger").fill("graph queue ell");
    await page.locator("#libraryText").fill("GraphQL");
    await page.getByRole("button", { name: "Add preference" }).click();
    await page
      .getByRole("button", { name: "Remove graph queue ell" })
      .waitFor();
    assert.equal(library.corrections.length, 1);
    await page.screenshot({
      path: path.join(root, "screenshots/macos-preferences.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 740, height: 580 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    assert.deepEqual(errors, []);
    process.stdout.write(
      "Desktop UI fixture checks passed: permissions/practice, native-only capture, one session, microphone/shortcut preferences, personalization, 740px window, no JS errors. Two labeled screenshots.\n",
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  process.stderr.write(error.stack + "\n");
  process.exit(1);
});
