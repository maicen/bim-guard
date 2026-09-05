/**
 * Signed-in session state, backed by Supabase Auth (Google OAuth). A single
 * instance is created below and shared everywhere — the browser's Supabase
 * session (not this class) is the actual source of truth; this just mirrors
 * it into runes so components can react to it.
 */

import type { Session, User } from "@supabase/supabase-js";
import { authApi } from "./api";
import { setAuthToken } from "./authToken";
import { isAuthConfigured, supabase } from "./supabaseClient";
import type { CurrentUserResponse, ProfileUpdatePayload } from "./types";

class AuthState {
  session = $state<Session | null>(null);
  profile = $state<CurrentUserResponse | null>(null);
  loading = $state(true);

  get user(): User | null {
    return this.session?.user ?? null;
  }

  constructor() {
    if (!isAuthConfigured) {
      this.loading = false;
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      this.session = data.session;
      setAuthToken(data.session?.access_token ?? null);
      this.loading = false;
      this.#loadProfile();
    });

    supabase.auth.onAuthStateChange((_event, session) => {
      this.session = session;
      setAuthToken(session?.access_token ?? null);
      this.loading = false;
      this.#loadProfile();
    });
  }

  async #loadProfile() {
    if (!this.session) {
      this.profile = null;
      return;
    }
    try {
      this.profile = await authApi.me(this.session.access_token);
    } catch {
      // Non-fatal: the header falls back to showing the Supabase user's
      // email, which is already on this.session.
      this.profile = null;
    }
  }

  /** Merge fields into the caller's profile and refresh the cached copy. */
  async updateProfile(updates: ProfileUpdatePayload): Promise<void> {
    if (!this.session) return;
    const updated = await authApi.updateProfile(this.session.access_token, updates);
    if (this.profile) this.profile = { ...this.profile, profile: updated };
  }

  /** Redirect to Google's consent screen; the browser comes back with a session. */
  async signInWithGoogle(): Promise<void> {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/` },
    });
    if (error) throw error;
  }

  async signOut(): Promise<void> {
    await supabase.auth.signOut();
    setAuthToken(null);
    this.profile = null;
  }
}

export const authState = new AuthState();
