/**
 * Severity banding, shared by every surface that shows a risk level.
 *
 * Both badge components previously carried their own colour tables and had
 * drifted apart (one rendered `high` as orange, the other as amber). This is the
 * single source of truth; the mapping is the one documented in DESIGN.md §10:
 * critical = rose, high = amber, medium = yellow, low = emerald.
 */
export type Severity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "data_quality"
  | "neutral";

export interface SeverityStyle {
  /** Pill background, border and text, tuned for the inverting slate surfaces. */
  badge: string;
  /** Solid dot / status-indicator fill. */
  dot: string;
}

export const SEVERITY_STYLES: Record<Severity, SeverityStyle> = {
  critical: {
    badge: "bg-rose-950/70 text-rose-300 border-rose-800/80 shadow-rose-950/20",
    dot: "bg-rose-400",
  },
  high: {
    badge: "bg-amber-950/70 text-amber-300 border-amber-800/80 shadow-amber-950/20",
    dot: "bg-amber-400",
  },
  medium: {
    badge: "bg-yellow-950/70 text-yellow-300 border-yellow-800/80 shadow-yellow-950/20",
    dot: "bg-yellow-400",
  },
  low: {
    badge: "bg-emerald-950/70 text-emerald-300 border-emerald-800/80 shadow-emerald-950/20",
    dot: "bg-emerald-400",
  },
  data_quality: {
    badge: "bg-indigo-950/70 text-indigo-300 border-indigo-800/80 shadow-indigo-950/20",
    dot: "bg-indigo-400",
  },
  neutral: {
    badge: "bg-slate-800 text-slate-300 border-slate-700 shadow-slate-900/20",
    dot: "bg-slate-400",
  },
};

/** Verdicts and legacy spellings that alias onto a band. */
const ALIASES: Record<string, Severity> = {
  fail: "critical",
  missing: "medium",
  missing_data: "medium",
  pass: "low",
  "data quality": "data_quality",
};

/** Collapse any stored severity/verdict string onto a canonical band. */
export function normalizeSeverity(value: string | null | undefined): Severity {
  const key = (value || "").toLowerCase().trim().replace(/-/g, "_");
  if (key in SEVERITY_STYLES) return key as Severity;
  return ALIASES[key] ?? ALIASES[key.replace(/_/g, " ")] ?? "neutral";
}

/** Human-readable label for a band. */
export function severityLabel(value: string | null | undefined): string {
  const band = normalizeSeverity(value);
  return band === "data_quality" ? "Data Quality" : (value || band);
}
