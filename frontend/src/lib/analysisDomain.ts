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
