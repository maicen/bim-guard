/**
 * Plumbing for Supabase's OAuth 2.1 server consent step, which lets MCP
 * clients (Claude, Cursor, ...) sign in to BIM-Guard through the browser.
 *
 * Supabase Auth redirects the user to `/oauth/consent?authorization_id=...`.
 * A user who is not signed in yet is sent to the normal login; the consent URL
 * is parked in sessionStorage (it survives the Google redirect in the same
 * tab) and resumed as soon as a session exists.
 */
import { supabase } from "./supabaseClient";

export const CONSENT_PATH = "/oauth/consent";
const PENDING_KEY = "bimguard.pendingOAuthConsent";

/** Remember the consent URL so it can be resumed after sign-in. */
export function stashPendingConsent(url: string): void {
  try {
    sessionStorage.setItem(PENDING_KEY, url);
  } catch {
    // Storage blocked: the user simply has to restart the client's sign-in.
  }
}

/** Resume a consent step that was interrupted by sign-in, if one is pending. */
export function watchPendingConsent(): void {
  supabase.auth.onAuthStateChange((_event, session) => {
    if (!session) return;
    try {
      const pending = sessionStorage.getItem(PENDING_KEY);
      if (!pending) return;
      sessionStorage.removeItem(PENDING_KEY);
      window.location.replace(pending);
    } catch {
      // Nothing to resume.
    }
  });
}
