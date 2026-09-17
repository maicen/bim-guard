// Exercise the viewer's mount contract under Node, and hold the Svelte host to it.
//
// WHY THIS EXISTS
//
//     On 2026-09-16 a browser showed "container.replaceChildren is not a
//     function" in the 3D viewer panel. The app passed the current
//     { viewport, details, drawings } object to a bundle from before that
//     split, which took the whole object as its single container element. A
//     plain object is truthy, so the bundle's own `if (!container)` guard let
//     it through and the first DOM call died.
//
//     Nothing caught it: the bundle needs a browser, so the argument shape was
//     never executed anywhere in CI. normalizeMounts() is that argument
//     handling, extracted so it can run here -- no THREE, no OBC, no DOM.
//
//     The second half of this file is a static cross-check: the version the
//     Svelte host expects, the version the bundle exports, and the ?v= token in
//     the import URL all have to agree, or the browser silently loads a
//     mismatched pair again.
//
//     node scripts/dev/viewer_contract_check.mjs
//
// Exit status is 0 when every assertion holds, 1 otherwise.

import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../..");
const mountsPath = path.resolve(repoRoot, "static/js/viewer/viewer-mounts.js");
const bundlePath = path.resolve(repoRoot, "static/js/viewer/ifc-viewer.js");
const hostPath = path.resolve(repoRoot, "frontend/src/lib/components/IfcViewer.svelte");

const { normalizeMounts, isElementLike, VIEWER_MOUNTS_API } = await import(
  pathToFileURL(mountsPath).href
);

let failures = 0;
function check(label, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) {
    console.log(`  ok   ${label}`);
  } else {
    console.error(`  FAIL ${label}\n       expected ${e}\n       actual   ${a}`);
    failures += 1;
  }
}
function checkThrows(label, fn, mustInclude) {
  try {
    fn();
    console.error(`  FAIL ${label}\n       expected a throw, got none`);
    failures += 1;
  } catch (err) {
    if (String(err.message).includes(mustInclude)) {
      console.log(`  ok   ${label}`);
    } else {
      console.error(`  FAIL ${label}\n       message lacks ${JSON.stringify(mustInclude)}\n       got ${err.message}`);
      failures += 1;
    }
  }
}

/** Minimal stand-in for a DOM element: element-like means "can take children". */
function fakeElement(name) {
  return { name, replaceChildren() {}, appendChild() {}, append() {} };
}

console.log("normalizeMounts — the shapes initViewer is actually called with");

const viewport = fakeElement("viewport");
const details = fakeElement("details");
const drawings = fakeElement("drawings");

// The current form.
const fromMounts = normalizeMounts({ viewport, details, drawings });
check("mounts object resolves all three",
  [fromMounts.viewport.name, fromMounts.details.name, fromMounts.drawings.name, fromMounts.form],
  ["viewport", "details", "drawings", "mounts"]);

// The regression: the Svelte host passes the viewport element itself, carrying
// the three mount names as properties, so an older bundle can mount into it
// natively. Resolving it must yield the element, not wrap it again.
const bridge = Object.assign(fakeElement("viewport"), { details, drawings });
bridge.viewport = bridge;
check("host bridge resolves to the viewport element itself",
  [normalizeMounts(bridge).viewport === bridge, normalizeMounts(bridge).details.name, normalizeMounts(bridge).form],
  [true, "details", "mounts"]);
check("that same bridge is element-like, so a legacy bundle can mount into it",
  isElementLike(bridge), true);

// The legacy form a pre-split caller uses.
check("bare element is accepted as the container",
  [normalizeMounts(viewport).viewport.name, normalizeMounts(viewport).details, normalizeMounts(viewport).form],
  ["viewport", null, "element"]);

// The id form.
check("element id is looked up",
  normalizeMounts("viewer-host", { getElementById: (id) => (id === "viewer-host" ? viewport : null) }).form,
  "id");
checkThrows("unknown id names the id",
  () => normalizeMounts("nope", { getElementById: () => null }),
  '"nope"');

// Non-element hosts must be rejected loudly rather than mounted into.
check("details that is not element-like is dropped, not passed through",
  normalizeMounts({ viewport, details: {}, drawings: undefined }).details, null);
checkThrows("mounts with a non-element viewport says so",
  () => normalizeMounts({ viewport: {}, details, drawings }),
  "mounts.viewport must be an element");

// The exact failure mode, from the other side: a bundle that only understands
// the legacy form gets the mounts object. normalizeMounts is what stops it.
checkThrows("a plain object is not mistaken for a container",
  () => normalizeMounts({ nope: true }),
  "expected a mount element");
checkThrows("null argument", () => normalizeMounts(null), "got null");
checkThrows("undefined argument", () => normalizeMounts(undefined), "got undefined");
checkThrows("stale-bundle case names the cause",
  () => normalizeMounts({ details, drawings }),
  "served from a different checkout");

check("isElementLike rejects a plain object", isElementLike({}), false);
check("isElementLike accepts anything with replaceChildren", isElementLike(viewport), true);

console.log("version handshake — app, bundle and cache-busting token agree");

const bundleSource = readFileSync(bundlePath, "utf8");
const hostSource = readFileSync(hostPath, "utf8");

const assetVersion = bundleSource.match(/VIEWER_ASSET_VERSION = "([^"]+)"/)?.[1];
const importUrl = hostSource.match(/\/static\/js\/viewer\/ifc-viewer\.js\?v=([^"']+)/)?.[1];
const hostExpects = Number(hostSource.match(/VIEWER_MOUNTS_API_EXPECTED = (\d+)/)?.[1]);

check("bundle declares an asset version", typeof assetVersion, "string");
check("host import URL carries that same version", importUrl, assetVersion);
check("host expects the contract the mounts module defines", hostExpects, VIEWER_MOUNTS_API);
check(
  "bundle re-exports the contract version",
  /export \{ VIEWER_MOUNTS_API \}/.test(bundleSource),
  true,
);
check(
  "initViewer normalises its argument rather than reading .viewport directly",
  /normalizeMounts\(mounts/.test(bundleSource),
  true,
);
check(
  "host checks the bundle's contract version before mounting",
  /mod\.VIEWER_MOUNTS_API !== VIEWER_MOUNTS_API_EXPECTED/.test(hostSource),
  true,
);
check(
  "host passes a bridge an older bundle can mount into",
  /Object\.assign\(viewportHost, \{\s*viewport: viewportHost/.test(hostSource),
  true,
);

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log("\nall checks passed");
