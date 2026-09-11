// Reduce a BCF 2.1 archive to just the topics that concern one IFC element.
//
// WHY
//
//     A findings deep link names one element, but the archive it arrives in
//     covers the whole project -- 1,384 topics and 5.1 MB for the hospital MEP
//     demo. Handing that to OBC.BCFTopics.load() costs minutes: every topic is
//     parsed, every viewpoint is instantiated, and the topics table re-renders
//     once per row. All of it is thrown away by a selection that wants one
//     topic. Filtering the bytes first turns that into a handful of entries.
//
// NO IMPORTS ON PURPOSE
//
//     JSZip is passed in rather than imported so this module runs unchanged in
//     the browser (JSZip from esm.sh, the same 3.10.1 that @thatopen/components
//     bundles for its own BCFTopics.load) and under Node against the npm
//     package (see scripts/dev/bcf_filter_check.mjs). The check script
//     therefore exercises the code that actually ships, not a copy of it.

/** Root-level entries every BCF archive keeps, whatever is filtered out. */
const ROOT_FILES = new Set(["bcf.version", "project.bcfp", "extensions.xsd"]);

/**
 * BCF priority vocabulary, most severe first. Matches what the exporter emits
 * (app/modules/phase_6/phase_6e_export.py maps RiskBand -> these four).
 */
export const PRIORITY_RANK = { critical: 0, major: 1, normal: 2, minor: 3 };

/** Rank a BCF priority string; unknown values sort last. */
export function priorityRank(priority) {
  return PRIORITY_RANK[String(priority || "").toLowerCase()] ?? 9;
}

/** The topic folder an archive entry belongs to, or null for a root entry. */
function topicFolderOf(path) {
  const slash = path.indexOf("/");
  if (slash <= 0) return null;
  return path.slice(0, slash);
}

/**
 * Return the topic folders whose markup or viewpoints reference `elementGuid`.
 *
 * Two shapes are matched, because two pipelines write the GUID differently:
 * `ElementGUID: <guid>` (persisted artifacts, pipeline_services._to_bcf_topic)
 * and `GUID: <guid>` (the /analyze/export archive, whose description
 * phase_6e_export._description builds under an ELEMENT heading). A viewpoint's
 * `IfcGuid="<guid>"` is matched too, which additionally catches topics where
 * the element is a partner component -- the other half of a galvanic couple,
 * the other side of a clash -- rather than the subject.
 */
async function keptFolders(zip, elementGuid) {
  const descriptionNeedles = [`ElementGUID: ${elementGuid}`, `GUID: ${elementGuid}`];
  const viewpointNeedle = `IfcGuid="${elementGuid}"`;
  const kept = new Set();

  // markup.bcf first: it is one file per topic and carries the subject, so it
  // decides most folders without touching the viewpoints at all.
  const markups = [];
  const viewpoints = [];
  zip.forEach((path, entry) => {
    if (entry.dir) return;
    if (path.endsWith("markup.bcf")) markups.push([path, entry]);
    else if (path.endsWith(".bcfv")) viewpoints.push([path, entry]);
  });

  for (const [path, entry] of markups) {
    const folder = topicFolderOf(path);
    if (!folder) continue;
    const text = await entry.async("string");
    if (descriptionNeedles.some((n) => text.includes(n))) kept.add(folder);
  }

  for (const [path, entry] of viewpoints) {
    const folder = topicFolderOf(path);
    if (!folder || kept.has(folder)) continue;
    const text = await entry.async("string");
    if (text.includes(viewpointNeedle)) kept.add(folder);
  }

  return kept;
}

/**
 * Build a new archive holding only the topics that reference `elementGuid`.
 *
 * @param {Function} JSZip The JSZip constructor (3.10.x).
 * @param {ArrayBuffer|Uint8Array} data The full archive.
 * @param {string} elementGuid The IFC GlobalId to keep topics for.
 * @returns {Promise<{data: Uint8Array|null, kept: number, entries: number,
 *   topics: number, folders: string[]}>} `data` is null when nothing matched,
 *   so the caller can report "not in this model" without loading an archive
 *   that would select something unrelated.
 */
export async function filterBcfArchive(JSZip, data, elementGuid) {
  const zip = await new JSZip().loadAsync(data);

  let entries = 0;
  let topics = 0;
  zip.forEach((path, entry) => {
    if (entry.dir) return;
    entries += 1;
    if (path.endsWith("markup.bcf")) topics += 1;
  });

  const folders = await keptFolders(zip, elementGuid);
  if (folders.size === 0) {
    return { data: null, kept: 0, entries, topics, folders: [] };
  }

  // Copied rather than deleted-in-place: a fresh archive of ~a dozen entries
  // is cheaper to generate than one that still carries 5,500 deleted slots,
  // and it cannot inherit state from the source zip.
  const out = new JSZip();
  const copies = [];
  zip.forEach((path, entry) => {
    if (entry.dir) return;
    const folder = topicFolderOf(path);
    const keep = folder === null ? ROOT_FILES.has(path) : folders.has(folder);
    if (keep) copies.push([path, entry]);
  });
  for (const [path, entry] of copies) {
    out.file(path, await entry.async("uint8array"), { binary: true });
  }

  // STORE, not DEFLATE: this archive is handed straight to BCFTopics.load in
  // the same tick and never leaves memory, so compressing it only costs time.
  const reduced = await out.generateAsync({ type: "uint8array", compression: "STORE" });
  return {
    data: reduced,
    kept: folders.size,
    entries,
    topics,
    folders: [...folders],
  };
}
