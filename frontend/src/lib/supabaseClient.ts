import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { supabaseUrl, supabaseAnonKey } from "./authConfig";

// Heavy module (~215 KiB): load it through `getSupabase()` in authConfig.ts,
// never with a static import from code the landing page reaches.

// A syntactically valid placeholder so createClient doesn't throw when auth
// isn't configured; isAuthConfigured gates every real call into it.
export const supabase: SupabaseClient = createClient(
  supabaseUrl || "https://placeholder.supabase.co",
  supabaseAnonKey || "placeholder-anon-key",
);
