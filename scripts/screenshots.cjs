/* Capture actual UI with isolated fictional API fixtures, and check interactions. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const { chromium } = require(
  require.resolve("playwright", {
    paths: [
      process.env.RMA_PLAYWRIGHT_DIR ||
        path.join(root, ".playwright/node_modules"),
    ],
  }),
);
const baseURL = process.env.RMA_BASE_URL || "http://127.0.0.1:5000";
(async () => {
  const launch = {
    headless: true,
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
    ],
  };
  if (process.env.RMA_BROWSER_PATH)
    launch.executablePath = process.env.RMA_BROWSER_PATH;
  const browser = await chromium.launch(launch);
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1080 },
      colorScheme: "light",
      reducedMotion: "reduce",
      permissions: ["microphone", "clipboard-read", "clipboard-write"],
    });
    const page = await context.newPage();
    const errors = [];
    const external = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      if (
        !request.url().startsWith(baseURL) &&
        !request.url().startsWith("data:")
      )
        external.push(request.url());
    });
    let words = [];
    let workspace = { draft: "", theme: "light", onboarding_complete: true };
    let library = { corrections: [], snippets: [], app_styles: [] };
    let settings = {
      model: "base",
      language: "en",
      llm_enabled: false,
      llm_model: "qwen2.5-0.5b",
    };
    let failUpload = false;
    let uploadCount = 0;
    await page.route("**/api/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      let data = {};
      if (url.pathname === "/api/workspace") {
        if (request.method() === "POST")
          workspace = { ...workspace, ...request.postDataJSON() };
        data = workspace;
      }
      if (url.pathname === "/api/personalization") {
        if (request.method() === "POST") library = request.postDataJSON();
        data = library;
      }
      if (url.pathname === "/api/history") data = { recordings: [], count: 0 };
      if (url.pathname === "/api/stats")
        data = { total_words: 0, total_recordings: 0, total_minutes: 0 };
      if (url.pathname === "/api/settings") {
        if (request.method() === "POST")
          settings = { ...settings, ...request.postDataJSON() };
        data =
          request.method() === "POST" ? { success: true, settings } : settings;
      }
      if (url.pathname === "/api/dictionary") {
        if (request.method() === "POST")
          words.push(request.postDataJSON().word);
        data = { success: true, words };
      }
      if (url.pathname.startsWith("/api/dictionary/")) {
        words = words.filter(
          (w) => w !== decodeURIComponent(url.pathname.split("/").pop()),
        );
        data = { success: true, words };
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(data),
      });
    });
    await page.route("**/transcribe", async (route) => {
      uploadCount++;
      await route.fulfill({
        status: failUpload ? 500 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          failUpload
            ? { error: "Fixture processing failure." }
            : {
                text: "A small idea can become something useful.",
                recording_id: "fixture_recording",
              },
        ),
      });
    });
    await page.goto(baseURL);
    await page.waitForSelector("#emptyAction");
    assert.equal(await page.locator("#statWords").textContent(), "0");
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    fs.mkdirSync(path.join(root, "screenshots"), { recursive: true });
    await page.locator("#toasts").evaluate((el) => el.replaceChildren());
    await page.screenshot({
      path: path.join(root, "screenshots/workspace-empty.png"),
      fullPage: true,
    });
    await page.locator("#emptyAction").click();
    await page.waitForSelector(".thought");
    assert.equal(await page.locator(".thought").count(), 3);
    await page.locator("#toasts").evaluate((el) => el.replaceChildren());
    await page.screenshot({
      path: path.join(root, "screenshots/workspace-sample.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Saved", exact: true }).click();
    assert.equal(await page.locator(".thought").count(), 1);
    await page
      .getByRole("button", { name: "All thoughts", exact: true })
      .click();
    await page.locator("#searchInput").fill("friction");
    assert.equal(await page.locator(".thought").count(), 1);
    await page.locator("#searchInput").fill("<script>alert(1)</script>");
    assert.equal(await page.locator(".thought").count(), 0);
    await page.locator("#searchInput").fill("");
    await page
      .getByRole("button", { name: "Move to scratchpad" })
      .first()
      .click();
    assert.match(
      await page.locator("#scratchpad").inputValue(),
      /best products/,
    );
    await page
      .locator("#scratchpad")
      .fill("A fictional draft, saved in this isolated browser.");
    await page.reload();
    assert.equal(
      await page.locator("#scratchpad").inputValue(),
      "A fictional draft, saved in this isolated browser.",
    );
    await page.locator("#toasts").evaluate((el) => el.replaceChildren());
    await page.screenshot({
      path: path.join(root, "screenshots/scratchpad.png"),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Dictionary", exact: false })
      .first()
      .click();
    await page.locator("#newWord").fill("GraphQL");
    await page.getByRole("button", { name: "Add word" }).click();
    await page.waitForSelector('[data-word="GraphQL"]');
    await page.getByRole("button", { name: "Remove GraphQL" }).click();
    await page.waitForFunction(
      () => document.getElementById("dictionaryCount").textContent === "0",
    );
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.locator("#languageSetting").selectOption("hi");
    await page.getByRole("button", { name: "Save preferences" }).click();
    await page.waitForFunction(() =>
      document
        .getElementById("settingsStatus")
        .textContent.startsWith("Saved."),
    );
    assert.equal(settings.language, "hi");
    await page.locator("#toasts").evaluate((el) => el.replaceChildren());
    await page.screenshot({
      path: path.join(root, "screenshots/settings.png"),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Dictation", exact: false })
      .first()
      .click();
    await page.keyboard.press("Shift+?");
    assert.equal(
      await page.locator("#helpDialog").evaluate((el) => el.open),
      true,
    );
    await page.keyboard.press("Escape");
    assert.equal(
      await page.locator("#helpDialog").evaluate((el) => el.open),
      false,
    );
    await page.keyboard.press("/");
    assert.equal(
      await page
        .locator("#searchInput")
        .evaluate((el) => el === document.activeElement),
      true,
    );
    await page.locator("#searchInput").blur();
    await page.locator("#themeBtn").click();
    await page.waitForFunction(
      () => document.documentElement.dataset.theme === "dark",
    );
    await page.locator("#emptyAction").click();
    await page.locator("#toasts").evaluate((el) => el.replaceChildren());
    await page.screenshot({
      path: path.join(root, "screenshots/workspace-dark.png"),
      fullPage: true,
    });
    await page.locator("#themeBtn").click();
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      "Mobile content overflows",
    );
    await page.locator("#toasts").evaluate((el) => el.replaceChildren());
    await page.screenshot({
      path: path.join(root, "screenshots/workspace-mobile.png"),
      fullPage: true,
    });
    await page.locator("#menuBtn").click();
    assert.equal(
      await page.locator("#menuBtn").getAttribute("aria-expanded"),
      "true",
    );
    await page.locator('#sidebar [data-view="settings"]').click();
    assert.equal(
      await page.locator("#menuBtn").getAttribute("aria-expanded"),
      "false",
    );
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      "Mobile settings overflow",
    );
    await page.setViewportSize({ width: 1440, height: 1080 });
    await page.locator('[data-view="dictation"]').first().click();
    await page.locator("#exitDemoBtn").click();
    // A synthetic browser microphone plus mocked transcription verifies client state, not model accuracy.
    await page.locator("#recordBtn").click();
    await page.waitForFunction(
      () =>
        document.getElementById("recordLabel").textContent ===
        "Finish dictating",
    );
    await page.waitForTimeout(800);
    await page.locator("#recordBtn").click();
    await page.waitForFunction(
      () =>
        document.getElementById("resultText").textContent ===
        "A small idea can become something useful.",
    );
    await page.locator("#draftResultBtn").click();
    assert.match(await page.locator("#scratchpad").inputValue(), /small idea/);
    await page.locator('[data-view="dictation"]').first().click();
    failUpload = true;
    await page.locator("#recordBtn").click();
    await page.waitForFunction(
      () =>
        document.getElementById("recordLabel").textContent ===
        "Finish dictating",
    );
    await page.waitForTimeout(800);
    await page.locator("#recordBtn").click();
    await page.waitForSelector("#retryUpload");
    failUpload = false;
    await page.locator("#retryUpload").click();
    await page.waitForFunction(() => !document.getElementById("retryUpload"));
    assert.equal(uploadCount, 3);
    // Denied microphone access is represented with a controlled browser API rejection.
    await page.evaluate(() => {
      navigator.mediaDevices.getUserMedia = async () => {
        throw new DOMException("Denied", "NotAllowedError");
      };
    });
    await page.locator("#recordBtn").click();
    await page.waitForFunction(
      () =>
        document.getElementById("recordLabel").textContent ===
        "Start dictating",
    );
    assert.match(
      await page.locator("#toasts").textContent(),
      /permission was declined/,
    );
    assert.deepEqual(errors, [], "Browser console errors");
    assert.deepEqual(external, [], "Unexpected third-party requests");
    console.log(
      "Browser checks passed: desktop/mobile overflow, sample/search/save filters, scratchpad persistence, dictionary, preferences, shortcuts, dialogs, theme, synthetic recording, retry, denied microphone. Captured six screens. All API/model responses were fixtures.",
    );
    await context.close();
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
