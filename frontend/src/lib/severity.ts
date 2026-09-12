/**
 * Severity banding, shared by every surface that shows a risk level.
 *
 * Both badge components previously carried their own colour tables and had
 * drifted apart (one rendered `high` as orange, the other as amber). This is the
 * single source of truth; the mapping is the one documented in DESIGN.md §10:
 * critical = rose, high = amber, medium = yellow, low = emerald.
 */
export type Severity = "critical" | "high" | "medium" | "low" | "data_quality" | "neutral";

export interface SeverityStyle {
  /** Pill background, border and text, tuned for the inverting slate surfaces. */
  badge: string;
  /** Solid dot / status-indicator fill. */
  dot: string;
}

export const SEVERITY_STYLES: Record<Severity, SeverityStyle> = {
  critical: {
    badge: "bg-critical-bg text-critical border-critical-border",
    dot: "bg-critical",
  },
  high: {
    badge: "bg-warning-bg text-warning border-warning-border",
    dot: "bg-warning",
  },
  medium: {
    badge: "bg-caution-bg text-caution border-caution-border",
    dot: "bg-caution",
  },
  low: {
    badge: "bg-success-bg text-success border-success-border",
    dot: "bg-success",
  },
  data_quality: {
    badge: "bg-info-bg text-info border-info-border",
    dot: "bg-info",
  },
  neutral: {
    badge: "bg-surface-overlay text-fg-secondary border-border-default",
    dot: "bg-fg-muted",
  },
};

/** Verdicts and legacy spellings that alias onto a band. */
const ALIASES: Record<string, Severity> = {
  fail: "critical",
  error: "critical",
  mandatory: "critical",
  warning: "high",
  caution: "medium",
  missing: "medium",
  missing_data: "medium",
  recommendation: "medium",
  advisory: "low",
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
  return band === "data_quality" ? "Data Quality" : value || band;
}
