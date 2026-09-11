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
