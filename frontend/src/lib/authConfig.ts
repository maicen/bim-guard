/**
 * Light-weight auth configuration, kept apart from supabaseClient.ts on purpose.
 *
 * PERF (mobile PageSpeed): `@supabase/supabase-js` is ~215 KiB of minified JS
 * (auth-js, realtime-js, storage-js, postgrest-js). Importing it statically put
 * all of it on the landing page's critical path, although a signed-out visitor
 * never talks to Supabase. Anything that only needs to know *whether* auth is
 * configured, or *whether a session could exist*, imports this file; code that
 * needs the client calls `getSupabase()`, which fetches it on demand. Never
 * import `./supabaseClient` statically from code reachable by the landing page.
 */
import type { SupabaseClient } from "@supabase/supabase-js";

export const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
export const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

/**
 * Whether sign-in is usable at all. False in any checkout that hasn't copied
 * frontend/.env.example to frontend/.env yet — deliberately non-fatal so the
 * rest of the app (which doesn't depend on auth yet) still runs.
 */
export const isAuthConfigured = Boolean(supabaseUrl && supabaseAnonKey);

if (!isAuthConfigured) {
  console.warn(
    "VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set — sign-in is disabled. " +
      "Copy frontend/.env.example to frontend/.env and fill them in to enable it.",
  );
}

/** Supabase keeps its session under an `sb-<ref>-auth-token` localStorage key. */
export function isSupabaseSessionKey(key: string | null): boolean {
  return !!key && key.startsWith("sb-") && key.endsWith("-auth-token");
}

/**
 * Whether a session *could* exist, decided synchronously at load: a stored
 * Supabase session, or an OAuth/magic-link return carrying tokens or a code in
 * the URL. With neither, `getSession()` can only resolve to "signed out".
 */
export function sessionPossible(): boolean {
  try {
    for (let i = 0; i < localStorage.length; i++) {
      if (isSupabaseSessionKey(localStorage.key(i))) return true;
    }
  } catch {
    // Storage blocked: Supabase can't persist a session either.
  }
  return /[?#&](access_token|refresh_token|code|error_description)=/.test(window.location.href);
}

let clientPromise: Promise<SupabaseClient> | null = null;

/** The shared Supabase client, fetched on first use (one chunk, one instance). */
export function getSupabase(): Promise<SupabaseClient> {
  clientPromise ??= import("./supabaseClient").then((m) => m.supabase);
  return clientPromise;
}
