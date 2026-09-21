/**
 * Room scope for a rule: which rooms an element must connect to for the rule to
 * govern it. Stored in the rule's `applies_when` as `room_type_any_of`.
 *
 * The room name is whatever the user types, and whatever their model calls its
 * rooms. The suggestions below are only quick picks: a built-in type also
 * matches its usual synonyms ("bedroom" finds "Guest Room", "Nursery"), and any
 * other text is matched against the room names as typed ("waiting" finds
 * "CENTRAL WAITING"). Spelling is never altered here.
 */

/**
 * Quick-pick room types. Mirrors the keys of ROOM_TYPE_KEYWORDS in
 * app/modules/room_types.py (a backend test keeps the two lists identical).
 */
export const ROOM_TYPE_SUGGESTIONS = [
  "bedroom",
  "living",
  "kitchen",
  "dining",
  "bathroom",
  "toilet",
  "laundry",
  "utility",
  "storage",
  "closet",
  "corridor",
  "lobby",
  "stair",
  "office",
  "garage",
  "balcony",
  "mechanical",
] as const;

/** The `applies_when` key this editor owns. Every other key is left untouched. */
export const ROOM_SCOPE_KEY = "room_type_any_of";

type Scope = Record<string, unknown> | null | undefined;

/** Split typed text on commas, semicolons or new lines; trim; drop repeats (case-insensitively). */
export function parseRoomLabels(text: string): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const part of text.split(/[,;\n]/)) {
    const label = part.trim();
    const key = label.toLowerCase();
    if (label && !seen.has(key)) {
      seen.add(key);
      labels.push(label);
    }
  }
  return labels;
}

/** The room labels a rule's scope already carries. */
export function roomLabelsFromScope(scope: Scope): string[] {
  const raw = scope?.[ROOM_SCOPE_KEY];
  if (Array.isArray(raw)) return raw.map(String);
  return typeof raw === "string" && raw.trim() ? [raw.trim()] : [];
}

/** The scope keys other than the room one, so the form can say they are kept. */
export function otherScopeKeys(scope: Scope): string[] {
  return Object.keys(scope ?? {}).filter((key) => key !== ROOM_SCOPE_KEY);
}

/**
 * The scope to save, or `undefined` when there is nothing to send.
 *
 * Only the room key is replaced; whatever else the rule's scope holds is kept.
 * A rule that had no scope and gets no room type sends nothing at all, so
 * leaving the field empty changes nothing. A rule that HAD a room type and has
 * it cleared sends the remaining scope (`{}` if none), which clears it.
 */
export function buildScope(existing: Scope, labels: string[]): Record<string, unknown> | undefined {
  const hadScope = !!existing && Object.keys(existing).length > 0;
  if (!hadScope && labels.length === 0) return undefined;
  const scope: Record<string, unknown> = { ...(existing ?? {}) };
  delete scope[ROOM_SCOPE_KEY];
  if (labels.length > 0) scope[ROOM_SCOPE_KEY] = labels;
  return scope;
}

/** Add the type to the typed list, or remove it if it is already there. */
export function toggleRoomLabel(text: string, label: string): string {
  const current = parseRoomLabels(text);
  const key = label.toLowerCase();
  const next = current.some((l) => l.toLowerCase() === key)
    ? current.filter((l) => l.toLowerCase() !== key)
    : [...current, label];
  return next.join(", ");
}

/** Split a result label ``BADROOM 1 [#Xy9k]`` into the room's name and its id tag. */
export function splitRoomLabel(label: string): { name: string; id: string } {
  const match = /^(.*?)\s*(\[#[^\]]+\])$/.exec(label);
  return match ? { name: match[1], id: match[2] } : { name: label, id: "" };
}
