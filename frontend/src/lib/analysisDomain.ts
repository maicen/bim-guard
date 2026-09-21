/**
 * Analysis-domain helpers shared by the wizard and the shell router.
 *
 * Mirrors `normalize_analysis_type` in app/constants.py: projects created
 * before the domain name was canonicalised still carry an old string
 * ('Architectural', 'Architecture'), and a project must open the view for
 * the domain it was actually created with.
 */
import type { AnalysisDomain } from "./types";

const ALIASES: Record<AnalysisDomain, string[]> = {
  Arch: ["arch", "architectural", "architecture"],
};

/** Collapse a stored or legacy analysis_type onto the canonical domain. */
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
  return "arch";
}

/** User-facing display label for an analysis domain with proper capitalization. */
export function formatAnalysisDomain(analysisType: string | null | undefined): string {
  return "Arch";
}

/**
 * The analysis slug whose run produced a finding, from its rule id.
 *
 * `/api/analyze/export?slug=...` re-runs (or reads the cache of) exactly the
 * slug it is given — see `export_analysis_report` in app/api/analyze.py, which
 * calls `run_analysis(slug, ...)`. RUNNABLE_SLUGS in
 * app/services/analysis_runner.py names only `architecture`, so every finding
 * routes there.
 */
export function analysisSlugForRuleId(
  ruleId: string | null | undefined,
  fallback: string = "architecture",
): string {
  return "architecture";
}

/**
 * The analysis slug for a finding row. Kept as a named entry point so callers
 * do not need to know the slug is currently a constant.
 */
export function analysisSlugForIssue(
  issue: { rule_id?: string | null; mechanism?: string | null } | null | undefined,
  fallback: string = "architecture",
): string {
  return "architecture";
}

/** Distinctive domain badge styling classes across the app. */
export function getDomainBadgeClasses(analysisType: string | null | undefined): string {
  return "border border-blue-800/50 bg-blue-950/60 text-blue-300";
}
