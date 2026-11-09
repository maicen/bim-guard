#!/usr/bin/env node
/**
 * Build a self-contained 3D viewer for air-gapped installs.
 *
 * static/js/viewer/ifc-viewer.js imports its engine (@thatopen/*, three, jszip)
 * from esm.sh and, at runtime, fetches the fragments worker and the web-ifc
 * WASM from unpkg and UI icons from the Iconify API. None of that is reachable
 * without internet. This script runs ONCE, at image build time on a machine
 * that does have internet, and emits a viewer directory that needs none:
 *
 *   <out>/ifc-viewer.js, bcf-filter.worker.js   bundles with every dependency inlined
 *   <out>/vendor/fragments-worker.mjs           replaces the unpkg worker download
 *   <out>/vendor/web-ifc*.wasm                  replaces the unpkg WASM download
 *   <out>/vendor/icons/<prefix>.json            replaces api.iconify.design
 *
 * The package versions are read from the esm.sh URLs in ifc-viewer.js, so the
 * source file stays the single place a version is pinned.
 *
 * Usage: node scripts/vendor_viewer.mjs --src static/js/viewer --out <dir>
 */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const arg = (name) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : undefined;
};
const SRC = path.resolve(arg("src") ?? "static/js/viewer");
const OUT = path.resolve(arg("out") ?? "");
if (!arg("out")) throw new Error("--out <dir> is required");
const VENDOR_BASE = arg("base") ?? "/static/js/viewer/vendor/";

// Hosts that must not survive in the output (checked at the end).
const FORBIDDEN = ["esm.sh", "unpkg.com", "api.iconify.design", "api.simplesvg.com", "api.unisvg.com", "thatopen.github.io"];

const entry = fs.readFileSync(path.join(SRC, "ifc-viewer.js"), "utf8");
const worker = fs.readFileSync(path.join(SRC, "bcf-filter.worker.js"), "utf8");

// ── 1. Pinned versions, straight from the import URLs ─────────────────────────
const deps = {};
for (const m of (entry + worker).matchAll(/https:\/\/esm\.sh\/((?:@[^/@]+\/)?[^@/?"]+)@([0-9][^/?"]*)/g)) deps[m[1]] = m[2];
const webIfc = entry.match(/unpkg\.com\/web-ifc@([0-9][^/"]*)/)?.[1];
if (!webIfc) throw new Error("could not find the pinned web-ifc version in ifc-viewer.js");
deps["web-ifc"] = webIfc;
deps["esbuild"] = "0.25.9";

// ── 2. Install them in a scratch directory (needs network, build time only) ────
const work = fs.mkdtempSync(path.join(os.tmpdir(), "bimguard-viewer-"));
fs.writeFileSync(path.join(work, "package.json"), JSON.stringify({ name: "viewer-vendor", private: true, type: "module", dependencies: deps }));
execFileSync("npm", ["install", "--no-audit", "--no-fund", "--silent"], { cwd: work, stdio: "inherit" });
const require_ = createRequire(path.join(work, "package.json"));
const esbuild = require_("esbuild");
const nm = (...p) => path.join(work, "node_modules", ...p);

// ── 3. Icons: collect the Iconify ids the UI packages reference ───────────────
const scanFiles = [path.join(SRC, "ifc-viewer.js"), nm("@thatopen/ui/dist/index.js"), nm("@thatopen/ui-obc/dist/index.js"), nm("@thatopen/components-front/dist/index.js")].filter(fs.existsSync);
const wanted = {};
for (const f of scanFiles) {
  for (const m of fs.readFileSync(f, "utf8").matchAll(/["'`]([a-z][a-z0-9-]*):([a-z0-9]+(?:-[a-z0-9]+)*)["'`]/g)) {
    (wanted[m[1]] ??= new Set()).add(m[2]);
  }
}
const iconDir = path.join(OUT, "vendor", "icons");
fs.mkdirSync(iconDir, { recursive: true });
const missingIcons = [];
for (const [prefix, names] of Object.entries(wanted)) {
  // A string like "http:foo" is not an icon; only prefixes with an icon pack matter.
  try {
    execFileSync("npm", ["install", "--no-audit", "--no-fund", "--silent", `@iconify-json/${prefix}`], { cwd: work, stdio: "ignore" });
  } catch {
    continue;
  }
  const set = JSON.parse(fs.readFileSync(nm("@iconify-json", prefix, "icons.json"), "utf8"));
  const icons = {}, aliases = {};
  for (const n of names) {
    if (set.icons[n]) icons[n] = set.icons[n];
    else if (set.aliases?.[n]) {
      aliases[n] = set.aliases[n];
      if (set.icons[set.aliases[n].parent]) icons[set.aliases[n].parent] = set.icons[set.aliases[n].parent];
    } else missingIcons.push(`${prefix}:${n}`);
  }
  if (!Object.keys(icons).length) continue;
  fs.writeFileSync(path.join(iconDir, `${prefix}.json`), JSON.stringify({ prefix, icons, aliases, width: set.width, height: set.height }));
}

// ── 4. Bundle ─────────────────────────────────────────────────────────────────
const neutralize = (src, keep = []) => {
  for (const host of FORBIDDEN) if (!keep.includes(host)) src = src.replaceAll(`https://${host}`, `${VENDOR_BASE}blocked`);
  return src;
};

const resolveEsmSh = {
  name: "esm-sh-to-node-modules",
  setup(build) {
    // https://esm.sh/@thatopen/components@3.4.8?external=... -> @thatopen/components
    // Resolve through esbuild (browser + ESM conditions), not Node's CommonJS rules.
    build.onResolve({ filter: /^https:\/\/esm\.sh\// }, (a) => {
      const spec = a.path.replace("https://esm.sh/", "").split("?")[0].replace(/@[0-9][^/]*$/, "");
      return build.resolve(spec, { resolveDir: work, kind: a.kind });
    });
    // "./bcf-filter.js?v=..." is a cache-buster for the browser; the file is local.
    build.onResolve({ filter: /^\.\/.*\?v=/ }, (a) => ({ path: path.join(a.resolveDir, a.path.split("?")[0]) }));
    // Point the bundled Iconify client at the icon data shipped with the viewer
    // instead of its public API hosts, so no icon request leaves the network.
    build.onLoad({ filter: /@thatopen[\\/]ui[\\/]dist[\\/]index\.js$/ }, (a) => {
      let src = fs.readFileSync(a.path, "utf8");
      src = src.replaceAll("https://api.iconify.design", `${VENDOR_BASE}icons`);
      src = src.replace(/\["https:\/\/api\.simplesvg\.com",\s*"https:\/\/api\.unisvg\.com"\]/, "[]");
      return { contents: neutralize(src), loader: "js" };
    });
    // Everything else we vendor can still *mention* a CDN in code that never runs
    // here (autoSetWasm, FragmentsModels.getWorker's unpkg download, a font
    // example). Rewrite those hosts to a local path so even a code path nobody
    // expects to reach cannot leave the network, and the check below can be strict.
    // (ifc-viewer.js keeps its esm.sh imports: onResolve above turns those into local files.)
    build.onLoad({ filter: /(@thatopen[\\/][^\\/]+[\\/]dist[\\/].*\.m?js|[\\/]ifc-viewer\.js)$/ }, (a) => ({
      contents: neutralize(fs.readFileSync(a.path, "utf8"), a.path.endsWith("ifc-viewer.js") ? ["esm.sh"] : []),
      loader: "js",
    }));
  },
};

await esbuild.build({
  entryPoints: [path.join(SRC, "ifc-viewer.js"), path.join(SRC, "bcf-filter.worker.js")],
  outdir: OUT,
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  minify: !process.argv.includes("--no-minify"),
  // Minified without this, @thatopen/ui's tooltip/animation code threw
  // "Failed to read the 'delay' property ... non-finite" and the loaded model never
  // appeared (verified in a browser against the same unminified bundle, which
  // rendered). The libraries read function/class names at runtime.
  keepNames: true,
  legalComments: "none",
  define: { __VIEWER_VENDOR_BASE__: JSON.stringify(VENDOR_BASE) },
  plugins: [resolveEsmSh],
  logLevel: "warning",
});

// ── 5. Runtime assets the bundle references by URL ────────────────────────────
const vendorDir = path.join(OUT, "vendor");
fs.copyFileSync(nm("@thatopen", "fragments", "dist", "Worker", "worker.mjs"), path.join(vendorDir, "fragments-worker.mjs"));
for (const f of fs.readdirSync(nm("web-ifc")).filter((n) => n.endsWith(".wasm"))) fs.copyFileSync(nm("web-ifc", f), path.join(vendorDir, f));
for (const f of ["bcf-filter.js", "bcf-colors.js", "viewer-mounts.js"]) fs.copyFileSync(path.join(SRC, f), path.join(OUT, f)); // kept for stale-cache URLs

// ── 6. Prove nothing external is left ─────────────────────────────────────────
const leftovers = [];
for (const f of ["ifc-viewer.js", "bcf-filter.worker.js", "vendor/fragments-worker.mjs"]) {
  const text = fs.readFileSync(path.join(OUT, f), "utf8");
  for (const host of FORBIDDEN) if (text.includes(host)) leftovers.push(`${f}: ${host}`);
}
if (missingIcons.length) console.warn(`[vendor_viewer] icons not found in their packs (will render blank): ${missingIcons.join(", ")}`);
if (leftovers.length) {
  console.error(`[vendor_viewer] FAILED: external hosts still referenced:\n  ${leftovers.join("\n  ")}`);
  process.exit(1);
}
console.log(`[vendor_viewer] ok: ${path.join(OUT, "ifc-viewer.js")} (${(fs.statSync(path.join(OUT, "ifc-viewer.js")).size / 1024).toFixed(0)} KiB), icons: ${fs.readdirSync(iconDir).join(", ")}`);
fs.rmSync(work, { recursive: true, force: true });
