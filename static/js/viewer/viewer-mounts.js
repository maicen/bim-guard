// Normalise whatever initViewer() was handed into the three mount elements.
//
// WHY
//
//     This module's entry point changed shape once already. It used to be
//     initViewer(containerOrId) -- one element (or its id), into which the
//     viewer put its whole workspace -- and it is now initViewer(mounts), an
//     object naming a viewport, a details dock and a drawings host separately.
//
//     Those two are silently incompatible in one direction. An old bundle
//     handed the new object takes it as the container, because a plain object
//     is truthy, and dies on the first DOM call against it:
//
//         container.replaceChildren is not a function
//
//     which is what a browser showed when the app was served from one checkout
//     and /static from another. Nothing in the message says "your static assets
//     are stale", and the app has no way to tell: the import resolves, the
//     module loads, the call signature "matches".
//
//     So: accept both shapes here, name the mismatch when it is real, and give
//     the caller a version to check against before it trusts the module at all.
//
// NO IMPORTS ON PURPOSE
//
//     Same rule as bcf-filter.js and bcf-colors.js: no THREE, no OBC, no DOM
//     globals, so scripts/dev/viewer_contract_check.mjs can exercise it under
//     plain Node. document is reached only through an injected lookup.

/**
 * Contract version for initViewer's argument.
 *
 * 1 = initViewer(containerOrId), the single-container form.
 * 2 = initViewer({ viewport, details, drawings }).
 *
 * The Svelte host checks this before mounting; a bundle that exports nothing is
 * an old one, and the message says so instead of letting a TypeError surface.
 */
export const VIEWER_MOUNTS_API = 2;

/** True for anything that can take children: a real element, or a test stub. */
export function isElementLike(value) {
  return Boolean(
    value &&
      typeof value === "object" &&
      typeof value.replaceChildren === "function",
  );
}

/** Short, safe description of a bad argument, for the thrown message. */
export function describeMountArgument(value) {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value !== "object") return typeof value;
  const keys = Object.keys(value).slice(0, 6).join(", ");
  return keys ? `object with keys: ${keys}` : "object with no keys";
}

/**
 * Resolve initViewer's argument to { viewport, details, drawings }.
 *
 * Accepts, in order:
 *
 * - `{ viewport, details, drawings }` -- the current form. `viewport` must be
 *   element-like; the other two are optional and may be null.
 * - an element -- the pre-2026-09 single-container form, still used by callers
 *   that predate the split. Details and drawings resolve to null, and the
 *   caller mounts everything into the one host.
 * - a string -- an element id, looked up through *getElementById*.
 *
 * @param input The argument initViewer received.
 * @param options.getElementById Injected `document.getElementById`; required
 *   only when *input* is a string.
 * @returns { viewport, details, drawings, form } where `form` is "mounts",
 *   "element" or "id", so the caller can log which shape it was given.
 * @throws {Error} With a message naming what arrived, when nothing usable can
 *   be resolved -- notably the stale-bundle case this module exists for.
 */
export function normalizeMounts(input, options = {}) {
  const { getElementById } = options;

  if (typeof input === "string") {
    const found = typeof getElementById === "function" ? getElementById(input) : null;
    if (!isElementLike(found)) {
      throw new Error(`initViewer: no element found for id ${JSON.stringify(input)}`);
    }
    return { viewport: found, details: null, drawings: null, form: "id" };
  }

  // An object carrying a viewport is the current form. Checked before the
  // element case on purpose: the Svelte host passes an object that is BOTH --
  // it names the three hosts and delegates replaceChildren to the viewport, so
  // that an older bundle can still mount into it.
  if (input && typeof input === "object" && "viewport" in input) {
    const { viewport, details = null, drawings = null } = input;
    if (!isElementLike(viewport)) {
      throw new Error(
        `initViewer: mounts.viewport must be an element, got ${describeMountArgument(viewport)}`,
      );
    }
    return {
      viewport,
      details: isElementLike(details) ? details : null,
      drawings: isElementLike(drawings) ? drawings : null,
      form: "mounts",
    };
  }

  if (isElementLike(input)) {
    return { viewport: input, details: null, drawings: null, form: "element" };
  }

  throw new Error(
    "initViewer: expected a mount element, an element id, or " +
      `{ viewport, details, drawings }; got ${describeMountArgument(input)}. ` +
      "If this says \"object with keys: viewport, details, drawings\", the app " +
      "is newer than the viewer bundle it loaded -- /static is being served " +
      "from a different checkout than the frontend.",
  );
}
