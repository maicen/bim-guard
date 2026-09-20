/**
 * Rule reliability tiers, shared by every surface that shows one.
 *
 * `ReliabilityBadge` (the grade on a row) and `ReliabilityLegend` (the reference
 * explaining the grades) both read from here so colours and wording can't drift
 * apart. The tier definitions are the project team's reliability guidance; the
 * grading itself lives in app/modules/rule_reliability.py and should be kept
 * consistent with the wording below.
 */
import type { RuleReliabilityLevel } from "./types";

export interface ReliabilityStyle {
  label: string;
  /** Pill background, border and text. */
  badge: string;
  /** Solid dot fill. */
  dot: string;
}

/** High = success, medium = caution, low = warning: a graded scale, not an error state. */
export const RELIABILITY_STYLES: Record<RuleReliabilityLevel, ReliabilityStyle> = {
  high: {
    label: "High",
    badge: "bg-success-bg text-success border-success-border",
    dot: "bg-success",
  },
  medium: {
    label: "Medium",
    badge: "bg-caution-bg text-caution border-caution-border",
    dot: "bg-caution",
  },
  low: {
    label: "Low",
    badge: "bg-warning-bg text-warning border-warning-border",
    dot: "bg-warning",
  },
};

export interface ReliabilityTier {
  level: RuleReliabilityLevel;
  title: string;
  /** What kind of IFC data this tier covers. */
  summary: string;
  /** A few typical properties, for recognition. */
  examples: string;
  /** Very short phrase for the one-line colour key. */
  keyPhrase: string;
}

/** Most to least reliable. */
export const RELIABILITY_TIERS: ReliabilityTier[] = [
  {
    level: "high",
    title: "High reliability",
    summary: "Standard IFC attributes, geometry, quantities, and relationships.",
    examples: "GUID, width, height, area, host wall, storey",
    keyPhrase: "standard IFC data",
  },
  {
    level: "medium",
    title: "Medium reliability",
    summary: "Standard property-set data that depends on correct Revit authoring and export.",
    examples: "fire rating, U-value, glazing material, acoustic rating",
    keyPhrase: "depends on Revit export",
  },
  {
    level: "low",
    title: "Low reliability",
    summary:
      "Custom parameters, calculated or derived values, or information that needs context IFC doesn't reliably store.",
    examples:
      "clear opening dimensions, escape compliance, smoke protection, manufacturer data, UserDefinedPartitioningType",
    keyPhrase: "custom or calculated",
  },
];

export const RELIABILITY_SCALE_NOTE =
  "Reliability decreases from direct standard IFC data, to authored or export-dependent properties, to calculated, custom, or externally referenced data.";

export const RELIABILITY_BASIS_NOTE =
  "Graded from the IFC property a rule checks, not from what the source document says, so it applies to extracted and manually added rules alike.";

export const RELIABILITY_BSDD_NOTE =
  "bSDD is a reference, not a verdict: being defined in the buildingSMART Data Dictionary shows a property is a standard one, not that real models fill it in reliably. For example, FireRating is defined in bSDD and is still Medium.";
