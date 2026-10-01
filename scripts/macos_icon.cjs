/* Render the repository's existing vector icon into standard macOS icon sizes. */
const fs = require("node:fs");
const path = require("node:path");
const cp = require("node:child_process");
const root = path.resolve(__dirname, "..");
const { chromium } = require(
  require.resolve("playwright", {
    paths: [
      process.env.RMA_PLAYWRIGHT_DIR ||
        path.join(root, ".playwright/node_modules"),
    ],
  }),
);
(async () => {
  const launch = { headless: true };
  if (process.env.RMA_BROWSER_PATH)
    launch.executablePath = process.env.RMA_BROWSER_PATH;
  const browser = await chromium.launch(launch);
  try {
    const page = await browser.newPage();
    const directory = path.join(root, "build/AppIcon.iconset");
    fs.mkdirSync(directory, { recursive: true });
    let svg = fs.readFileSync(
      path.join(root, "src/apps/web/static/icon.svg"),
      "utf8",
    );
    await page.setContent(
      `<style>html,body{margin:0;background:transparent}svg{width:100vw;height:100vh}</style>${svg}`,
    );
    for (const size of [16, 32, 128, 256, 512]) {
      for (const scale of [1, 2]) {
        await page.setViewportSize({
          width: size * scale,
          height: size * scale,
        });
        await page.screenshot({
          path: path.join(
            directory,
            `icon_${size}x${size}${scale === 2 ? "@2x" : ""}.png`,
          ),
          omitBackground: true,
        });
      }
    }
    cp.execFileSync("iconutil", [
      "-c",
      "icns",
      directory,
      "-o",
      path.join(root, "packaging/macos/AppIcon.icns"),
    ]);
    process.stdout.write("Rendered Mac app icon from the existing SVG.\n");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  process.stderr.write(error.message + "\n");
  process.exit(1);
});
