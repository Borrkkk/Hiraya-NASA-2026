// Pre-flight for the demo: node scripts/check-demo.mjs [base-url]
//   1. every prefetched frame in the manifest exists (files on disk)
//   2. if a base URL is given (default http://localhost:3000), the app serves them
//   3. the sky backdrop (Aladin's DSS2 tiles from IRSA) is reachable
// Exit code 1 if 1 or 2 fail. Step 3 only warns: the demo still works without it,
// the sky around the SPHEREx picture is just black.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "demo", "barnard");
const base = process.argv[2] ?? "http://localhost:3000";
let bad = 0;
const fail = (m) => (console.error("FAIL", m), bad++);

const manifest = JSON.parse(readFileSync(join(root, "manifest.json"), "utf8"));
let files = 0;
for (const l of manifest.area.levels)
  for (const e of manifest.epochs)
    for (const b of e.bands) {
      files++;
      if (!existsSync(join(root, "frames", `L${l.level}`, e.id, `${b}.png`))) fail(`missing L${l.level}/${e.id}/${b}.png`);
    }
console.log(`${files} frames listed, ${manifest.epochs.length} observations, ${manifest.sources.length} sources`);

try {
  const r = await fetch(`${base}/demo/barnard/manifest.json`);
  r.ok ? console.log(`app serves the data at ${base}`) : fail(`${base} answered ${r.status}`);
  const page = await fetch(`${base}/explore`);
  page.ok ? console.log("explore page loads") : fail(`/explore answered ${page.status}`);
} catch {
  fail(`could not reach ${base}: is the app running?`);
}

try {
  const r = await fetch("https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color/properties", { signal: AbortSignal.timeout(6000) });
  console.log(r.ok ? "sky backdrop (IRSA DSS2) reachable" : `WARN backdrop answered ${r.status}`);
} catch {
  console.warn("WARN sky backdrop unreachable: the demo works, but the surrounding sky and the Compare layers will be empty");
}
process.exit(bad ? 1 : 0);
