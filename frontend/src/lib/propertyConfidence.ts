/**
 * Property resolution confidence styling, shared by every surface that shows
 * which pass of the IFC property-resolution cascade actually supplied a
 * rule's evaluated value (authored Pset vs. type-inherited vs. geometry
 * estimate, etc.). The category shape itself mirrors
 * app/modules/property_confidence.py and lives in types.ts as
 * `PropertyConfidence`, alongside the app's other backend contract mirrors;
 * this file only owns the visual mapping, the same split as severity.ts vs.
 * the Severity type it defines locally (Severity has no backend contract to
 * mirror, so it stays self-contained there — PropertyConfidence does, so it
 * lives with the other contracts instead).
 */
import type { PropertyConfidence } from "./types";

export type PropertyConfidenceId = PropertyConfidence["id"];

export interface PropertyConfidenceStyle {
  /** Meter bar fill for filled segments. */
  bar: string;
  /** Label text color. */
  text: string;
}

export const PROPERTY_CONFIDENCE_STYLES: Record<PropertyConfidenceId, PropertyConfidenceStyle> = {
  authored: { bar: "bg-success", text: "text-success" },
  derived: { bar: "bg-success", text: "text-success" },
  type_inherited: { bar: "bg-caution", text: "text-caution" },
  alias: { bar: "bg-caution", text: "text-caution" },
  fallback: { bar: "bg-warning", text: "text-warning" },
  geometry_estimate: { bar: "bg-warning", text: "text-warning" },
  unresolved: { bar: "bg-fg-muted", text: "text-fg-muted" },
};

/** Fallback shown when an element carries no property_confidence at all
 * (older cached results, or a check path that never resolved a property). */
export const UNKNOWN_PROPERTY_CONFIDENCE: PropertyConfidence = {
  id: "unresolved",
  label: "Unresolved",
  description: "No value could be found for this property through any resolution pass.",
  rank: 7,
  meter_level: 0,
};
