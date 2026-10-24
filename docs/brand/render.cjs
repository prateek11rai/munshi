// Renders the brand pages to PNG at their exact sizes with Playwright and the system Chrome.
// Usage: NODE_PATH=<folder holding playwright> node docs/brand/render.cjs [--scale 2 --out <dir>] [name ...]
const path = require("path");
const { chromium } = require("playwright");

const IMG = path.join(__dirname, "..", "img");
const PAGES = {
  banner: ["banner.html", "banner.png", 1280, 400],
  "devto-cover": ["devto-cover.html", "devto-cover.png", 1000, 420],
  "social-preview": ["social-preview.html", "social-preview.png", 1280, 640],
  architecture: ["architecture.html", "diagrams/architecture.png", 1600, 0],
  "writer-run": ["writer-run.html", "diagrams/writer-run.png", 1600, 0],
  "privacy-gates": ["privacy-gates.html", "diagrams/privacy-gates.png", 1600, 0],
  "data-model": ["data-model.html", "diagrams/data-model.png", 1600, 0],
};

function option(name, fallback) {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : process.argv[i + 1];
}

(async () => {
  const scale = Number(option("--scale", "1"));
  const out = option("--out", IMG);
  const flags = new Set(["--scale", "--out"]);
  const names = process.argv.slice(2).filter((a, i, all) => !flags.has(a) && !flags.has(all[i - 1]));
  const browser = await chromium.launch({ channel: "chrome" });
  for (const name of names.length ? names : Object.keys(PAGES)) {
    const [html, png, width, height] = PAGES[name];
    // Diagrams (height 0) take the height of their content.
    const page = await browser.newPage({ viewport: { width, height: height || 400 }, deviceScaleFactor: scale });
    page.on("console", (msg) => console.log(`  ${name}: ${msg.text()}`));
    await page.route(/^(?!file:)/, (route) => route.abort());
    await page.goto("file://" + path.join(__dirname, html));
    const target = path.join(out, scale === 1 ? png : png.replace(/\.png$/, `@${scale}x.png`));
    await page.screenshot({ path: target, fullPage: !height });
    console.log(`${name}: ${target}`);
    await page.close();
  }
  await browser.close();
})();
