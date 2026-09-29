/**
 * Check categories group a rule's results under its element type (e.g.
 * "Fire and Smoke Protection" under Windows). The list itself is data —
 * `rulesApi.listCheckCategories()` — and names repeat across element types,
 * so rules and results reference a category by id.
 */
import type { RuleCheckCategory } from "./types";

/** Heading shown for rules that have no check category. */
export const UNCATEGORIZED_LABEL = "Uncategorized";

/**
 * Select value for "no category". It is also what the API takes to clear a
 * category (id 0), and bits-ui Select treats "" as "nothing selected".
 */
export const UNCATEGORIZED_VALUE = "0";

/** True when `category` is offered for `targetIfcClass` (or for every element type). */
export function categoryAppliesTo(category: RuleCheckCategory, targetIfcClass?: string | null): boolean {
  const target = targetIfcClass?.trim().toLowerCase();
  return (
    !target ||
    !category.target_ifc_classes.length ||
    category.target_ifc_classes.some((c) => c.toLowerCase() === target)
  );
}

/**
 * Options for a category picker, "Uncategorized" first. With `targetIfcClass`
 * only categories for that element type (or for every type) are offered;
 * without it every category is listed, labelled with its element types.
 */
export function checkCategoryOptions(categories: RuleCheckCategory[], targetIfcClass?: string | null) {
  const hasTarget = !!targetIfcClass?.trim();
  return [
    { value: UNCATEGORIZED_VALUE, label: UNCATEGORIZED_LABEL },
    ...categories
      .filter((c) => categoryAppliesTo(c, targetIfcClass))
      .map((c) => ({
        value: String(c.id),
        label:
          !hasTarget && c.target_ifc_classes.length
            ? `${c.name} (${c.target_ifc_classes.join(", ")})`
            : c.name,
      })),
  ];
}

/** The picker value for a stored category id. */
export function checkCategoryOption(categoryId: number | null | undefined): string {
  return categoryId ? String(categoryId) : UNCATEGORIZED_VALUE;
}

/** Map a picker value back to the id the API expects (0 clears the category). */
export function checkCategoryFromOption(value: string): number {
  return Number(value) || 0;
}
