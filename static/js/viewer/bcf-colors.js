// Turn a BCF viewpoint's Coloring block into highlighter-ready colour groups.
//
// WHY
//
//     bcf_generator._viewpoint_xml already writes the right colours: the
//     finding's subject takes its risk band's colour (_BAND_COLOURS: Low
//     FF107C10, Medium FFFF8C00, High FFC05000, Critical FFC00000) and the
//     partners implicated in it -- the other side of a clash, the other half
//     of a galvanic couple -- take PARTNER_COLOUR (FF0070C0). The viewer threw
//     all of that away: Viewpoint.go() was patched to highlight the whole
//     selection in one fixed red, so a Medium finding and a Critical one were
//     the same colour on screen.
//
// NO IMPORTS ON PURPOSE
//
//     Same rule as bcf-filter.js: this module runs unchanged in the browser
//     (loaded by ifc-viewer.js from /static) and under Node in
//     scripts/dev/viewer_color_check.mjs, so the check exercises the code that
//     ships rather than a copy of it. Nothing here touches THREE, OBC or the
//     DOM; the caller owns all of that.

/** BCF stores colours as ARGB or RGB hex, no leading '#'. */
const HEX_RE = /^[0-9a-fA-F]+$/;

/**
 * Normalise one BCF colour string to 6-digit RGB hex, or null if unusable.
 *
 * BCF 2.1 writes ARGB ("FFC00000"); some authoring tools write plain RGB
 * ("C00000") and some prefix '#'. The alpha channel is dropped rather than
 * honoured: the highlighter style sets its own opacity, and a half-transparent
 * risk colour reads as a different band.
 */
export function normalizeBcfColor(raw) {
  const text = String(raw ?? "").trim().replace(/^#/, "");
  if (!HEX_RE.test(text)) return null;
  if (text.length === 8) return text.slice(2).toUpperCase();
  if (text.length === 6) return text.toUpperCase();
  return null;
}

/**
 * Group a viewpoint's componentColors into [{ hex, guids }], most-severe first.
 *
 * `componentColors` is what @thatopen/components parses out of the Coloring
 * block: a Map-like of colour -> component GUIDs. Entries whose colour or guid
 * list is unusable are dropped rather than guessed at, so a malformed archive
 * loses its colours and keeps its selection.
 *
 * @param componentColors Map/DataMap of colour string -> iterable of guids.
 * @returns Array of { hex, guids: string[] }, empty when there is nothing to colour.
 */
export function colorGroupsFromComponentColors(componentColors) {
  if (!componentColors || typeof componentColors.entries !== "function") return [];
  const byHex = new Map();
  for (const [rawColor, rawGuids] of componentColors.entries()) {
    const hex = normalizeBcfColor(rawColor);
    if (!hex) continue;
    const guids = [];
    for (const guid of rawGuids ?? []) {
      const id = String(guid ?? "").trim();
      if (id) guids.push(id);
    }
    if (guids.length === 0) continue;
    // One colour can appear twice if an archive splits a band across blocks.
    const existing = byHex.get(hex);
    if (existing) existing.push(...guids);
    else byHex.set(hex, guids);
  }
  return [...byHex.entries()]
    .map(([hex, guids]) => ({ hex, guids }))
    .sort((a, b) => bandRank(a.hex) - bandRank(b.hex));
}

/**
 * Severity order for the colours bcf_generator emits, most severe first.
 *
 * Only used to make the highlight order deterministic when one element carries
 * two colours; an unknown colour sorts last and is still applied.
 */
const BAND_COLOUR_RANK = {
  C00000: 0, // Critical
  C05000: 1, // High
  FF8C00: 2, // Medium
  "107C10": 3, // Low
  "0070C0": 4, // Partner
  888888: 5, // Unknown band fallback
};

export function bandRank(hex) {
  return BAND_COLOUR_RANK[String(hex || "").toUpperCase()] ?? 9;
}

/** Highlighter style name for a colour, stable so styles are reused per hex. */
export function styleNameForColor(hex) {
  return `bimguard-bcf-${String(hex || "").toUpperCase()}`;
}
