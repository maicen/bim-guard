/**
 * Analysis-domain helpers shared by the wizard and the shell router.
 *
 * Mirrors `normalize_analysis_type` in app/constants.py: projects created
 * before the domain name was canonicalised still carry an old string
 * ('Architectural', 'Architecture'), and a project must open the view for
 * the domain it was actually created with.
 */
import type { SelectOption } from "./components/ui/Select.svelte";
import type { AnalysisDomain } from "./types";

/**
 * Rule-category options for the rule/ruleset-folder editors. Arch is the only
 * category `public.rules`/`public.rule_folders` accept (`CHECK (category =
 * 'Arch')`), so this is a single-entry list rather than a real choice — kept
 * as one shared constant so it isn't hand-duplicated across RuleForm,
 * RulesetFolderModal, RuleBulkEditModal and RulesetFolderBulkEditModal.
 */
export const ARCH_CATEGORY_OPTIONS: SelectOption[] = [
  { value: "Arch", label: "Arch (Architectural)" },
];

/**
 * Mechanism options for the same editors. GC-001/CC-001/MC-001/SEISMIC were
 * the removed Piping/Seismic engines' mechanism scopes; CODE (building code)
 * is the only mechanism Arch rules use today.
 */
export const ARCH_MECHANISM_OPTIONS: SelectOption[] = [
  { value: "CODE", label: "CODE (Building Code)" },
];

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
