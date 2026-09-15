// Exercise the browser BCF filter under Node, against a real exported archive.
//
// This imports static/js/viewer/bcf-filter.js -- the module the viewer itself
// loads -- and injects the npm JSZip instead of the esm.sh one, so what is
// asserted here is the code that ships rather than a transcription of it.
//
// Deliberately not a pytest: it needs Node, a zip library that is not a
// project dependency, and a multi-megabyte fixture that is not in the repo.
//
// USAGE
//
//     # fetch the fixture once (any BCF 2.1 archive will do)
//     curl -H "Authorization: Bearer $TOKEN" -o /tmp/export1917.bcf \
//       "http://127.0.0.1:8001/api/analyze/export?project_id=1917&slug=corrosion&fmt=bcf"
//
//     # jszip is dev-only and intentionally not in frontend/package.json
//     npm_config_prefix=/tmp/jszip-tmp npm i -g --prefix /tmp/jszip-tmp jszip@3.10.1
//     NODE_PATH=/tmp/jszip-tmp/node_modules \
//       node scripts/dev/bcf_filter_check.mjs /tmp/export1917.bcf 20KeDvTYrO59MhDS4MnkZ9
//
// Exit status is 0 when every assertion holds, 1 otherwise.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const [, , archivePath, elementGuid, expectedTitleArg] = process.argv;
if (!archivePath || !elementGuid) {
  console.error("usage: node bcf_filter_check.mjs <archive.bcf> <elementGuid> [expectedTitleSubstring]");
  process.exit(2);
}
const expectedTitle = expectedTitleArg ?? "PIP-MC-L03-0007";

// JSZip is resolved through NODE_PATH / the ambient install rather than a
// project dependency -- see the usage note above.
const require = createRequire(import.meta.url);
const JSZip = require("jszip");

const here = path.dirname(fileURLToPath(import.meta.url));
const filterUrl = pathToFileURL(path.resolve(here, "../../static/js/viewer/bcf-filter.js"));
const { filterBcfArchive, priorityRank } = await import(filterUrl.href);

const raw = readFileSync(archivePath);
console.log(`archive: ${archivePath} (${raw.length} bytes)`);

const started = performance.now();
const result = await filterBcfArchive(JSZip, raw, elementGuid);
const elapsedMs = performance.now() - started;

console.log(`entries=${result.entries} topics=${result.topics} read=${result.read}`);
console.log(`kept=${result.kept} ms=${elapsedMs.toFixed(0)}`);
console.log(`reduced archive bytes=${result.data ? result.data.length : 0}`);
console.log(`shrink: ${(raw.length / (result.data?.length || 1)).toFixed(1)}x smaller`);

const failures = [];
if (result.kept < 1) failures.push(`kept=${result.kept}, expected at least 1`);
if (!result.data) failures.push("no reduced archive produced");

// The reduced archive must still be a readable BCF: re-parse it and read the
// titles and priorities back out, which is what BCFTopics.load will do.
let titles = [];
if (result.data) {
  const reparsed = await new JSZip().loadAsync(result.data);
  const markups = [];
  reparsed.forEach((p, e) => {
    if (!e.dir && p.endsWith("markup.bcf")) markups.push([p, e]);
  });
  const keptTopicGuids = new Set();
  const relationRefs = [];
  for (const [, entry] of markups) {
    const xml = await entry.async("string");
    const title = /<Title>([\s\S]*?)<\/Title>/.exec(xml)?.[1] ?? "(untitled)";
    const priority = /<Priority>([\s\S]*?)<\/Priority>/.exec(xml)?.[1] ?? "";
    titles.push({ title, priority });
    const own = /<Topic\b[^>]*\bGuid="([^"]+)"/.exec(xml)?.[1];
    if (own) keptTopicGuids.add(own);
    for (const m of xml.matchAll(/<RelatedTopic\s+Guid="([^"]+)"/g)) {
      relationRefs.push({ title, guid: m[1] });
    }
  }

  // The reduced archive must be internally consistent. A RelatedTopic pointing
  // at a topic that was filtered out resolves to undefined in
  // CUI.sections.topicRelations, which reads .guid off it and throws inside
  // lit's render -- synchronously, before the element gets highlighted.
  const dangling = relationRefs.filter((r) => !keptTopicGuids.has(r.guid));
  console.log(
    `relatedTopic refs=${relationRefs.length} dangling=${dangling.length} ` +
      `(stripped by filter=${result.strippedRelations})`,
  );
  if (dangling.length) {
    failures.push(
      `${dangling.length} dangling RelatedTopic refs remain, e.g. ` +
        `"${dangling[0].title.slice(0, 40)}" -> ${dangling[0].guid}`,
    );
  }
  titles.sort((a, b) => priorityRank(a.priority) - priorityRank(b.priority));

  console.log(`reduced topics=${markups.length}`);
  for (const { title, priority } of titles) {
    console.log(`  [${priority || "-"}] ${title.slice(0, 90)}`);
  }
  if (markups.length !== result.kept) {
    failures.push(`reduced archive has ${markups.length} topics, kept said ${result.kept}`);
  }
  if (!titles.some((t) => t.title.includes(expectedTitle))) {
    failures.push(`no title contains ${expectedTitle}`);
  }
  // The topic that sorts first is the one the viewer selects and frames, so
  // that -- not the literal band -- is the invariant worth asserting. A
  // critical finding must outrank the element's other topics; an element whose
  // findings are all Normal still has to resolve to the expected one.
  if (titles.length && !titles[0].title.includes(expectedTitle)) {
    failures.push(
      `first topic is "${titles[0].title.slice(0, 60)}" [${titles[0].priority}], ` +
        `expected one containing ${expectedTitle}`,
    );
  }
}

// A GUID that is in no topic must yield no archive at all, so the viewer shows
// "not in this model" rather than selecting something unrelated.
const miss = await filterBcfArchive(JSZip, raw, "0000000000000000000000");
if (miss.data !== null || miss.kept !== 0) {
  failures.push(`unknown GUID kept ${miss.kept} topics, expected 0 and no archive`);
} else {
  console.log("unknown GUID -> kept=0, no archive (correct)");
}

if (failures.length) {
  console.error("\nFAILED:");
  for (const f of failures) console.error("  - " + f);
  process.exit(1);
}
console.log("\nOK: all assertions passed");
