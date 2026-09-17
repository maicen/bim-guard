/**
 * Analysis-domain helpers shared by the wizard and the shell router.
 *
 * Mirrors `normalize_analysis_type` in app/constants.py: projects created
 * before the domain names were canonicalised still carry the old strings
 * ('Architectural', 'Piping (Corrosive)', 'Halo'), and a project must open the
 * view for the domain it was actually created with.
 */
import type { AnalysisDomain } from "./types";

const ALIASES: Record<AnalysisDomain, string[]> = {
  Arch: ["arch", "architectural", "architecture"],
  Piping: ["piping", "piping (corrosive)", "corrosion"],
  seismic: ["seismic", "halo", "piping (seismic)", "blue halo"],
};

/** Collapse a stored or legacy analysis_type onto one of the three domains. */
export function normalizeAnalysisDomain(
  analysisType: string | null | undefined,
  fallback: AnalysisDomain = "Arch",
): AnalysisDomain {
  const value = (analysisType || "").trim().toLowerCase();
  if (!value) return fallback;
  for (const [domain, aliases] of Object.entries(ALIASES) as [AnalysisDomain, string[]][]) {
    if (aliases.includes(value)) return domain;
  }
  return fallback;
}

/** The App view id that runs the analysis for a project's domain. */
export function viewForAnalysisDomain(analysisType: string | null | undefined): string {
  switch (normalizeAnalysisDomain(analysisType)) {
    case "Piping":
      return "piping";
    case "seismic":
      return "seismic";
    default:
      return "arch";
  }
}

/** User-facing display label for an analysis domain with proper capitalization. */
export function formatAnalysisDomain(analysisType: string | null | undefined): string {
  switch (normalizeAnalysisDomain(analysisType)) {
    case "Piping":
      return "Piping";
    case "seismic":
      return "Seismic";
    default:
      return "Arch";
  }
}

/**
 * The analysis slug whose run produced a finding, from its rule id.
 *
 * `/api/analyze/export?slug=...` re-runs (or reads the cache of) exactly the
 * slug it is given — see `export_analysis_report` in app/api/analyze.py, which
 * calls `run_analysis(slug, ...)`. A viewer deep link that hardcodes one slug
 * therefore fetches the wrong archive for every finding from another engine:
 * a seismic SB-001 topic is simply absent from the corrosion BCF, which
 * surfaces as "element could not be located in this model".
 *
 * Mapping (engine code prefix -> slug, mirroring RUNNABLE_SLUGS in
 * app/services/analysis_runner.py):
 *
 * - `SB` (Blue Halo seismic clearance) -> `seismic`
 * - `GC`, `CC`, `MC`, `MM`, `XM` (the five corrosion engines) -> `corrosion`
 * - anything architectural -> `architecture`
 *
 * An unrecognised id falls back to *fallback*, which callers set to the slug
 * of the run on screen, so a new engine keeps working as it does today rather
 * than resolving to a wrong-but-confident slug.
 */
const RULE_PREFIX_SLUGS: Record<string, string> = {
  SB: "seismic",
  GC: "corrosion",
  CC: "corrosion",
  MC: "corrosion",
  MM: "corrosion",
  XM: "corrosion",
  ARCH: "architecture",
};

export function analysisSlugForRuleId(
  ruleId: string | null | undefined,
  fallback: string = "corrosion",
): string {
  const id = (ruleId || "").trim().toUpperCase();
  if (!id) return fallback;
  if (id.startsWith("ARCH") || id.startsWith("BUILDING-CODE")) return "architecture";
  // Rule ids are "<two-letter engine code>-<three digits>" (GC-001, SB-001),
  // and a finding's mechanism string repeats that code as its first token.
  const prefix = id.slice(0, 2);
  return RULE_PREFIX_SLUGS[prefix] ?? fallback;
}

/**
 * The analysis slug for a finding row, preferring its rule id and falling back
 * to its mechanism string (both carry the engine code; only `rule_id` is
 * guaranteed non-empty on every Issue).
 */
export function analysisSlugForIssue(
  issue: { rule_id?: string | null; mechanism?: string | null } | null | undefined,
  fallback: string = "corrosion",
): string {
  if (!issue) return fallback;
  const fromRule = analysisSlugForRuleId(issue.rule_id, "");
  if (fromRule) return fromRule;
  return analysisSlugForRuleId(issue.mechanism, fallback);
}

/** Distinctive domain badge styling classes across the app. */
export function getDomainBadgeClasses(analysisType: string | null | undefined): string {
  switch (normalizeAnalysisDomain(analysisType)) {
    case "Piping":
      return "border border-amber-800/50 bg-amber-950/60 text-amber-300";
    case "seismic":
      return "border border-purple-800/50 bg-purple-950/60 text-purple-300";
    default:
      return "border border-blue-800/50 bg-blue-950/60 text-blue-300";
  }
}
