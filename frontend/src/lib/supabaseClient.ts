import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

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

// A syntactically valid placeholder so createClient doesn't throw when auth
// isn't configured; isAuthConfigured gates every real call into it.
export const supabase: SupabaseClient = createClient(
  supabaseUrl || "https://placeholder.supabase.co",
  supabaseAnonKey || "placeholder-anon-key",
);
