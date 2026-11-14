// Renders each cutout in src/data/cutouts.json with Aladin Lite in headless
// Chrome and writes public/sky/<id>.webp. The images are real survey data,
// committed to the repo so the app never depends on a live cutout service.
//
//   pnpm bake:cutouts            # all cutouts
//   pnpm bake:cutouts orion m31  # only these ids
import { chromium } from "playwright-core";
import { createServer } from "node:http";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const spec = JSON.parse(await readFile(path.join(root, "src/data/cutouts.json"), "utf8"));
const only = new Set(process.argv.slice(2));
const todo = spec.cutouts.filter((c) => only.size === 0 || only.has(c.id));
const outDir = path.join(root, "public/sky");
await mkdir(outDir, { recursive: true });

const aladinJs = await readFile(path.join(root, "node_modules/aladin-lite/dist/aladin.js"));
const page = `<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;background:#050608}</style><div id="a"></div>
<script type="module">
import A from "/aladin.js";
window.bake = async (o) => {
  await A.init;
  const el = document.getElementById("a");
  el.style.width = o.w + "px"; el.style.height = o.h + "px";
  const al = A.aladin(el, {
    survey: o.survey, target: o.ra + " " + o.dec, fov: o.fov,
    projection: "SIN", cooFrame: "ICRS", backgroundColor: "rgb(5, 6, 8)",
    showReticle: false, showZoomControl: false, showLayersControl: false,
    showFullscreenControl: false, showGotoControl: false, showProjectionControl: false,
    showFrame: false, showFov: false, showCooLocation: false, showStatusBar: false,
    showContextMenu: false, showSimbadPointerControl: false, showCooGridControl: false,
    showSettingsControl: false, showShareControl: false, log: false,
  });
  // (aladin.getViewDataURL ignores its options, so call the view directly.)
  // Tiles stream in; wait until two frames a second apart are identical.
  let prev = "";
  for (let i = 0; i < 45; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    const url = await al.view.getCanvasDataURL("image/png", undefined, undefined, false);
    if (i >= 3 && url === prev) return await webp(url, o.quality);
    prev = url;
  }
  return await webp(prev, o.quality);
};
// Star fields are noisy, so re-encode as WebP to keep each cutout small.
async function webp(pngUrl, quality) {
  const img = new Image();
  img.src = pngUrl;
  await img.decode();
  const c = document.createElement("canvas");
  c.width = img.width; c.height = img.height;
  c.getContext("2d").drawImage(img, 0, 0);
  return c.toDataURL("image/webp", quality);
}
</script>`;

const server = createServer((req, res) => {
  if (req.url === "/aladin.js") {
    res.writeHead(200, { "content-type": "text/javascript" });
    res.end(aladinJs);
  } else {
    res.writeHead(200, { "content-type": "text/html" });
    res.end(page);
  }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
});
try {
  for (const c of todo) {
    const p = await browser.newPage({ viewport: { width: spec.width, height: spec.height }, deviceScaleFactor: 1 });
    p.on("pageerror", (e) => console.error(`  [${c.id}] page error:`, e.message));
    await p.goto(origin);
    const dataUrl = await p.evaluate(
      (o) => window.bake(o),
      { ...c, survey: spec.surveys[c.survey].url, w: spec.width, h: spec.height, quality: spec.quality },
    );
    const buf = Buffer.from(dataUrl.split(",")[1], "base64");
    await writeFile(path.join(outDir, `${c.id}.webp`), buf);
    console.log(`${c.id}.webp  ${(buf.length / 1024).toFixed(0)} KB`);
    await p.close();
  }
} finally {
  await browser.close();
  server.close();
}
