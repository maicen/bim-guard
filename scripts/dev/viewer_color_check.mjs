// Exercise the viewer's BCF colour grouping under Node.
//
// This imports static/js/viewer/bcf-colors.js -- the module the viewer itself
// loads -- so what is asserted here is the code that ships rather than a
// transcription of it. Unlike bcf_filter_check.mjs it needs no fixture and no
// third-party package, so it runs anywhere Node does:
//
//     node scripts/dev/viewer_color_check.mjs
//
// Exit status is 0 when every assertion holds, 1 otherwise.
//
// The colours asserted below are the ones app/modules/reporter/bcf_generator.py
// writes (_BAND_COLOURS and PARTNER_COLOUR). If that table changes, this fails.

import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const moduleUrl = pathToFileURL(path.resolve(here, "../../static/js/viewer/bcf-colors.js"));
const { normalizeBcfColor, colorGroupsFromComponentColors, bandRank, styleNameForColor } =
  await import(moduleUrl.href);

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

console.log("normalizeBcfColor");
// BCF 2.1 writes ARGB; the alpha channel is dropped, not honoured.
check("ARGB critical", normalizeBcfColor("FFC00000"), "C00000");
check("ARGB high", normalizeBcfColor("FFC05000"), "C05000");
check("ARGB medium", normalizeBcfColor("FFFF8C00"), "FF8C00");
check("ARGB low", normalizeBcfColor("FF107C10"), "107C10");
check("ARGB partner", normalizeBcfColor("FF0070C0"), "0070C0");
check("plain RGB", normalizeBcfColor("C00000"), "C00000");
check("leading hash", normalizeBcfColor("#ff8c00"), "FF8C00");
check("garbage", normalizeBcfColor("not-a-colour"), null);
check("empty", normalizeBcfColor(""), null);
check("null", normalizeBcfColor(null), null);

console.log("colorGroupsFromComponentColors");
// What @thatopen/components parses out of a Coloring block: colour -> guids.
const viewpointColors = new Map([
  ["FFFF8C00", ["1SUBJECT0000000000000A"]],
  ["FF0070C0", ["2PARTNER0000000000000B", "3PARTNER0000000000000C"]],
]);
check("groups", colorGroupsFromComponentColors(viewpointColors), [
  { hex: "FF8C00", guids: ["1SUBJECT0000000000000A"] },
  { hex: "0070C0", guids: ["2PARTNER0000000000000B", "3PARTNER0000000000000C"] },
]);

// Most severe first, so a guid carrying two colours ends up painted by the
// more severe one (the last highlight wins in the viewer).
check(
  "severity order",
  colorGroupsFromComponentColors(
    new Map([
      ["FF107C10", ["low"]],
      ["FFC00000", ["critical"]],
      ["FFFF8C00", ["medium"]],
      ["FFC05000", ["high"]],
    ]),
  ).map((g) => g.hex),
  ["C00000", "C05000", "FF8C00", "107C10"],
);

check("no colours -> empty", colorGroupsFromComponentColors(new Map()), []);
check("undefined -> empty", colorGroupsFromComponentColors(undefined), []);
check(
  "unusable entries dropped",
  colorGroupsFromComponentColors(
    new Map([
      ["nonsense", ["x"]],
      ["FFC00000", []],
      ["FFC05000", ["  "]],
      ["FF107C10", ["kept"]],
    ]),
  ),
  [{ hex: "107C10", guids: ["kept"] }],
);
check(
  "same colour in two blocks merges",
  colorGroupsFromComponentColors(
    new Map([
      ["FFC00000", ["a"]],
      ["#C00000", ["b"]],
    ]),
  ),
  [{ hex: "C00000", guids: ["a", "b"] }],
);

console.log("misc");
check("unknown colour sorts last", bandRank("ABCDEF") > bandRank("888888"), true);
check("style name is stable per hex", styleNameForColor("c00000"), "bimguard-bcf-C00000");
check(
  "critical and medium get different styles",
  styleNameForColor("C00000") !== styleNameForColor("FF8C00"),
  true,
);

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log("\nall checks passed");
