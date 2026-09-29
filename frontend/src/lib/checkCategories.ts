/**
 * Check categories group a rule's results under its element type (e.g.
 * "Fire and Smoke Protection" under Windows). The list itself is data —
 * `rulesApi.listCheckCategories()` — so only the "none" handling lives here.
 */
import type { RuleCheckCategory } from "./types";

/** Heading shown for rules that have no check category. */
export const UNCATEGORIZED_LABEL = "Uncategorized";

/**
 * Select value standing in for "no category": bits-ui Select treats "" as
 * "nothing selected", so the explicit choice needs a real value.
 */
export const UNCATEGORIZED_VALUE = "__uncategorized__";

/** Options for a category picker, "Uncategorized" first. */
export function checkCategoryOptions(categories: RuleCheckCategory[]) {
  return [
    { value: UNCATEGORIZED_VALUE, label: UNCATEGORIZED_LABEL },
    ...categories.map((c) => ({ value: c.name, label: c.name })),
  ];
}

/** Map a picker value back to what the API expects ("" clears the category). */
export function checkCategoryFromOption(value: string): string {
  return value === UNCATEGORIZED_VALUE ? "" : value;
}
