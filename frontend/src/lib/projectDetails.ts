/**
 * Step 1 (Details) of the New Project wizard: the required-field lock-chain
 * and the client-name pick-list filter.
 *
 * Kept free of Svelte so the rules can be exercised directly
 * (tests/test_project_details_lock_chain.py runs this module under Node);
 * ProjectDetailsStep.svelte wraps them in $derived.
 */

/**
 * The required Details fields, in the order they unlock. Each is disabled
 * until every field before it has a non-empty value. Optional fields
 * (description, size, buildings, floors) are not part of the chain.
 */
export const REQUIRED_DETAIL_FIELDS = [
  { key: "clientName", label: "client name", verb: "Enter" },
  { key: "name", label: "project name", verb: "Enter" },
  { key: "shortName", label: "short name", verb: "Enter" },
  { key: "projectCode", label: "project code", verb: "Enter" },
  { key: "country", label: "jurisdiction", verb: "Select" },
  { key: "projectType", label: "project type", verb: "Select" },
] as const;

export type RequiredDetailField = (typeof REQUIRED_DETAIL_FIELDS)[number]["key"];

export type RequiredDetailValues = Record<RequiredDetailField, string | null | undefined>;

/**
 * For each required field, the hint naming what must be filled before it can
 * be edited, or null when the field is unlocked.
 *
 * The hint names the earliest empty field ahead of it -- that is the one the
 * user has to fill next -- so clearing an earlier field re-locks everything
 * after it without discarding what was typed there.
 */
export function detailLocks(
  values: RequiredDetailValues,
): Record<RequiredDetailField, string | null> {
  const locks = {} as Record<RequiredDetailField, string | null>;
  let blocker: (typeof REQUIRED_DETAIL_FIELDS)[number] | null = null;
  for (const field of REQUIRED_DETAIL_FIELDS) {
    locks[field.key] = blocker ? `${blocker.verb} the ${blocker.label} first.` : null;
    if (!blocker && !(values[field.key] ?? "").trim()) blocker = field;
  }
  return locks;
}

/**
 * Client names from earlier projects that match what has been typed so far.
 *
 * Case-insensitive substring match; an entry identical to the query is left
 * out, since offering back exactly what is already in the field adds nothing.
 */
export function matchingClientNames(known: readonly string[], query: string): string[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [...known];
  return known.filter((clientName) => {
    const candidate = clientName.toLowerCase();
    return candidate !== needle && candidate.includes(needle);
  });
}
