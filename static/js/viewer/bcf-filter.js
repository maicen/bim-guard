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

  // Only these two extensions are ever decompressed. Snapshots are PNGs of a
  // viewpoint and can be several KB each; there are ~1,384 of them here and
  // none can contain the GUID, so they are copied verbatim later and never
  // read.
  const markups = [];
  const viewpoints = [];
  zip.forEach((path, entry) => {
    if (entry.dir) return;
    if (path.endsWith("markup.bcf")) markups.push([path, entry]);
    else if (path.endsWith(".bcfv")) viewpoints.push([path, entry]);
  });

  // Read in parallel, not one awaited call after another.
  //
  // This is the whole performance story. JSZip's async() drives its inflate
  // through a chunked stream that yields to the event loop between chunks, so
  // an awaited loop pays the browser's minimum timer delay per entry rather
  // than per batch: 2,768 sequential reads measured 58.6 s in Edge against
  // 365 ms in Node, where the same clamp does not apply. Started together they
  // interleave and the wall time collapses to roughly the decompression cost.
  //
  // Chunked rather than one giant Promise.all so an archive far larger than
  // this one cannot hold every inflated entry in memory at once.
  const CHUNK = 512;
  const scan = async (pairs, matches) => {
    const hits = [];
    for (let i = 0; i < pairs.length; i += CHUNK) {
      const slice = pairs.slice(i, i + CHUNK);
      const texts = await Promise.all(slice.map(([, entry]) => entry.async("string")));
      for (let j = 0; j < slice.length; j += 1) {
        const folder = topicFolderOf(slice[j][0]);
        if (folder && matches(texts[j])) hits.push(folder);
      }
    }
    return hits;
  };

  // markup.bcf carries the subject element and decides most folders.
  for (const folder of await scan(markups, (t) =>
    descriptionNeedles.some((n) => t.includes(n)),
  )) {
    kept.add(folder);
  }

  // Viewpoints add the topics where this element is a partner component -- the
  // other half of a galvanic couple, the other side of a clash -- rather than
  // the subject. Folders already kept are skipped so they are never inflated.
  const remaining = viewpoints.filter(([path]) => {
    const folder = topicFolderOf(path);
    return folder && !kept.has(folder);
  });
  for (const folder of await scan(remaining, (t) => t.includes(viewpointNeedle))) {
    kept.add(folder);
  }

  return { kept, read: markups.length + remaining.length };
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

  const { kept: folders, read } = await keptFolders(zip, elementGuid);
  if (folders.size === 0) {
    return { data: null, kept: 0, entries, topics, read, folders: [] };
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
  // Raw bytes, in parallel: no decode/re-encode, and snapshots stay opaque.
  const bytes = await Promise.all(copies.map(([, entry]) => entry.async("uint8array")));
  for (let i = 0; i < copies.length; i += 1) {
    out.file(copies[i][0], bytes[i], { binary: true });
  }

  // STORE, not DEFLATE: this archive is handed straight to BCFTopics.load in
  // the same tick and never leaves memory, so compressing it only costs time.
  const reduced = await out.generateAsync({ type: "uint8array", compression: "STORE" });
  return {
    data: reduced,
    kept: folders.size,
    entries,
    topics,
    read,
    folders: [...folders],
  };
}
