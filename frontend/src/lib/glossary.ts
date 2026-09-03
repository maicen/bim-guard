/**
 * Domain glossary for hover-card previews.
 *
 * The UI is dense with codes that are meaningful to a BIM information manager
 * and opaque to everyone else — `S3`, `P01.01`, `SHARED`, `XM-001`. Each entry
 * gives the short expansion shown as a card heading plus a one-or-two sentence
 * explanation, so the code can stay compact in tables while the meaning stays
 * one hover away.
 *
 * Sources: BS EN ISO 19650-1/-2 (suitability + revision coding, CDE workflow
 * states) and the engine module headers under `app/engines/` and
 * `app/modules/comparator/` for the mechanism descriptions.
 */

export interface GlossaryEntry {
  /** Human-readable expansion of the code. */
  label: string;
  /** One to two sentences of plain-language explanation. */
  description: string;
  /** Optional standard or ruleset the definition comes from. */
  reference?: string;
}

/**
 * ISO 19650 suitability (status) codes.
 *
 * Grouped by container state: S-codes while the container is shared inside the
 * delivery team, A- and B-codes once the appointing party has authorized it,
 * D-codes when issued outside the delivery team, CR for the as-constructed
 * record.
 */
export const SUITABILITY_CODES: Record<string, GlossaryEntry> = {
  S0: {
    label: "Work in progress",
    description:
      "Initial status. The container is still being authored and has not been checked, reviewed or approved for use by anyone outside its own task team.",
  },
  S1: {
    label: "Suitable for coordination",
    description:
      "Shared with the wider delivery team so other disciplines can coordinate their own design against it. Not approved for construction.",
  },
  S2: {
    label: "Suitable for information",
    description:
      "Shared for reference only. Other teams may read it but must not develop coordinated design decisions on top of it.",
  },
  S3: {
    label: "Suitable for review and comment",
    description:
      "Issued into a formal review cycle. Reviewers are expected to raise comments that the author must resolve before the next revision.",
  },
  S4: {
    label: "Suitable for stage approval",
    description:
      "Submitted for approval at a project stage gate. Approval moves the container towards a published, contractual revision.",
  },
  S5: {
    label: "Suitable for manufacture / procurement",
    description:
      "Released so that fabrication, procurement or long-lead ordering can begin against the information it carries.",
  },
  S6: {
    label: "Suitable for PIM authorization",
    description:
      "Submitted for the appointing party to authorize the Project Information Model at the end of a delivery phase.",
  },
  S7: {
    label: "Suitable for AIM acceptance",
    description:
      "Submitted for acceptance into the Asset Information Model, i.e. handover into operation.",
  },
  A: {
    label: "Authorized and accepted",
    description:
      "Published. The appointing party has authorized the container; the suffix number is the acceptance sequence (A1, A2, …).",
  },
  B: {
    label: "Partial sign-off, with comments",
    description:
      "Published with reservations. Accepted for use but carrying outstanding comments that must be closed out (B1, B2, …).",
  },
  D1: {
    label: "Issued for costing",
    description:
      "Released outside the delivery team so a cost plan or estimate can be produced against it.",
  },
  D2: {
    label: "Issued for tender",
    description:
      "Released as part of a tender package. Tenderers price the works from this revision.",
  },
  D3: {
    label: "Issued for contractor design",
    description: "Released to a contractor as the basis for their own contractor-designed portion.",
  },
  D4: {
    label: "Issued for manufacture",
    description: "Released for manufacture or procurement outside the delivery team.",
  },
  CR: {
    label: "As-constructed record",
    description:
      "The verified record of what was actually built, forming part of the asset handover information.",
  },
};

/** Look up a suitability code, tolerating the numbered A1/B2 forms. */
export function describeSuitability(code: string | null | undefined): GlossaryEntry {
  const key = (code || "S0").toUpperCase().trim();
  const direct = SUITABILITY_CODES[key];
  if (direct) return { ...direct, reference: "BS EN ISO 19650-2" };

  // A1..An and B1..Bn share a definition; only the sequence number differs.
  const family = key.charAt(0);
  if ((family === "A" || family === "B") && SUITABILITY_CODES[family]) {
    return { ...SUITABILITY_CODES[family], reference: "BS EN ISO 19650-2" };
  }

  return {
    label: "Unrecognised status code",
    description:
      "This code is not part of the standard ISO 19650 suitability table. Check the project's information standard for a locally defined status.",
    reference: "BS EN ISO 19650-2",
  };
}

/** CDE workflow states and what each one permits. */
export const CDE_STATES: Record<string, GlossaryEntry> = {
  WIP: {
    label: "Work in Progress",
    description:
      "Owned by a single task team and visible only to them. Containers here are unchecked and must not be used by other disciplines.",
  },
  SHARED: {
    label: "Shared",
    description:
      "Checked, reviewed and approved by the task team, then made visible to the whole delivery team for coordination, review or comment.",
  },
  PUBLISHED: {
    label: "Published",
    description:
      "Authorized by the appointing party and released for use — the contractual, referenceable revision of the information.",
  },
  ARCHIVED: {
    label: "Archived",
    description:
      "Superseded but retained. Kept as an auditable record of what was issued and when; never deleted, never used as current information.",
  },
};

/** Look up a CDE state, falling back to a WIP-shaped description. */
export function describeCdeState(state: string | null | undefined): GlossaryEntry {
  const key = (state || "WIP").toUpperCase().trim();
  return (
    CDE_STATES[key] || {
      label: key || "Unknown",
      description:
        "Not one of the four ISO 19650 common data environment states (WIP, SHARED, PUBLISHED, ARCHIVED).",
    }
  );
}

/**
 * Explain an ISO 19650 revision code such as `P01.01` or `C03.02`.
 *
 * Prefix `P` marks a preliminary revision (work in progress or shared);
 * prefix `C` marks a contractual revision issued after authorization. The
 * first number is the major revision, the second the minor iteration within it.
 */
export function describeRevision(code: string | null | undefined): GlossaryEntry {
  const raw = (code || "P01.01").toUpperCase().trim();
  const match = raw.match(/^([PC])(\d+)(?:\.(\d+))?$/);

  if (!match) {
    return {
      label: raw,
      description:
        "Does not match the ISO 19650 revision pattern (P or C, a major number, then an optional minor number — for example P01.01 or C02).",
      reference: "BS EN ISO 19650-2",
    };
  }

  const [, prefix, major, minor] = match;
  const stage =
    prefix === "P"
      ? "Preliminary revision — issued before the container was authorized, i.e. while it is work in progress or shared."
      : "Contractual revision — issued after authorization, so it carries contractual weight.";
  const counters = minor
    ? `Major revision ${Number(major)}, iteration ${Number(minor)} within it.`
    : `Major revision ${Number(major)}.`;

  return {
    label: prefix === "P" ? "Preliminary revision" : "Contractual revision",
    description: `${stage} ${counters}`,
    reference: "BS EN ISO 19650-2",
  };
}

/**
 * Compliance mechanisms — the engine or rule family a finding came from.
 * Descriptions mirror the engine module headers so the UI and the kernels
 * cannot drift apart in what they claim to check.
 */
export const MECHANISMS: Record<string, GlossaryEntry> = {
  "GC-001": {
    label: "Galvanic corrosion",
    description:
      "Scores dissimilar-metal couples from the driving voltage between them, the anode-to-cathode area ratio, and how aggressive the surrounding environment is.",
    reference: "NASA-STD-6012 · IMOA Design Manual · ruleset BIMGUARD-GC-001",
  },
  "CC-001": {
    label: "Crevice corrosion",
    description:
      "Scores gaps, laps and shielded joints where stagnant electrolyte collects, weighing joint geometry against the alloy's critical crevice temperature and the environment.",
    reference: "EN ISO 15329 · ASTM G48-B · ruleset BIMGUARD-CC-001",
  },
  "MC-001": {
    label: "Microbially influenced corrosion",
    description:
      "Scores biofilm risk in water systems from flow velocity, operating temperature and dead-leg length — the same conditions that drive Legionella control.",
    reference: "CIBSE TM13 · HSE HSG274 · ruleset BIMGUARD-MC-001",
  },
  "MM-001": {
    label: "Material–media compatibility",
    description:
      "Scores whether a pipe material can safely carry the medium inside it, adjusted for environment severity and operating temperature. Unmapped pairings raise a data-quality finding rather than a silent pass.",
    reference: "ruleset BIMGUARD-MM-001",
  },
  "XM-001": {
    label: "Cross-material contamination",
    description:
      "Scores galvanic couples formed where dissimilar materials meet at a joint or share an electrolyte loop, and names which side sacrifices.",
    reference: "ruleset BIMGUARD-XM-001 (shares the GC-001 galvanic series)",
  },
  "SB-001": {
    label: "Seismic bracing clearance",
    description:
      "Blue Halo kernel. Checks that services keep the required clearance envelope for seismic movement and bracing.",
    reference: "EN 1998-1 · DIN 4149 · ruleset BIMGUARD-SB-001",
  },
  CODE: {
    label: "Code compliance rule",
    description:
      "A declarative rule evaluated against IFC property values — the building-code and information-requirement checks, as opposed to a physics kernel.",
  },
  "ARCH-EGRESS-001": {
    label: "Egress analysis",
    description:
      "Builds a space-connectivity graph from the model to measure travel distance to an exit and count storey exits.",
    reference: "ruleset BIMGUARD-ARCH-EGRESS-001",
  },
  "ARCH-SPATIAL-001": {
    label: "Spatial daylight",
    description:
      "Reads IfcRelSpaceBoundary relationships to check window glazing area against floor area for each space.",
    reference: "ruleset BIMGUARD-ARCH-SPATIAL-001",
  },
};

/**
 * Look up a mechanism by code, tolerating the `BIMGUARD-` prefix and the
 * two-letter engine ids (`GC`, `CC`, …) used by the analysis engine selector.
 */
export function describeMechanism(code: string | null | undefined): GlossaryEntry | null {
  const key = (code || "")
    .toUpperCase()
    .trim()
    .replace(/^BIMGUARD-/, "");
  if (!key) return null;
  if (MECHANISMS[key]) return MECHANISMS[key];
  if (MECHANISMS[`${key}-001`]) return MECHANISMS[`${key}-001`];
  // Findings carry sub-rule references such as "SB-001.01".
  const base = key.split(".")[0];
  return MECHANISMS[base] || null;
}

/** Severity bands, and what each one asks the reviewer to do. */
export const SEVERITY_BANDS: Record<string, GlossaryEntry> = {
  critical: {
    label: "Critical",
    description:
      "A mandatory requirement is breached or a failure mode is active. Resolve before the container can progress past review.",
  },
  high: {
    label: "High risk",
    description:
      "Strong evidence of a degradation or compliance risk. Needs a design change or a recorded, justified acceptance.",
  },
  medium: {
    label: "Medium risk",
    description:
      "Conditions favour a problem developing over time. Worth mitigating, but it does not block the current stage on its own.",
  },
  low: {
    label: "Low risk",
    description:
      "Scored and assessed as acceptable. Kept in the report as evidence that the element was actually checked.",
  },
  data_quality: {
    label: "Data quality",
    description:
      "The model does not carry enough information to score this element — a missing material, medium, temperature or environment class. Reported instead of passing it silently.",
  },
};

/** Look up a severity band description. */
export function describeSeverity(band: string | null | undefined): GlossaryEntry | null {
  const key = (band || "").toLowerCase().trim().replace(/[\s-]/g, "_");
  if (key === "fail") return SEVERITY_BANDS.critical;
  if (key === "pass") return SEVERITY_BANDS.low;
  if (key === "missing" || key === "missing_data") return SEVERITY_BANDS.data_quality;
  return SEVERITY_BANDS[key] || null;
}
