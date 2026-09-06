/**
 * Signed-in session state, backed by Supabase Auth (Google OAuth or
 * email/password). A single instance is created below and shared everywhere
 * — the browser's Supabase session (not this class) is the actual source of
 * truth; this just mirrors it into runes so components can react to it.
 */

import type { Session, User } from "@supabase/supabase-js";
import { authApi, clearTenantCaches } from "./api";
import { setAuthToken, setActiveOrgId, setAuthReady } from "./authToken";
import { isAuthConfigured, supabase } from "./supabaseClient";
import type { CurrentUserResponse, ProfileUpdatePayload } from "./types";

class AuthState {
  session = $state<Session | null>(null);
  profile = $state<CurrentUserResponse | null>(null);
  loading = $state(true);

  #activeOrgIdOverride = $state<number | null>(null);

  get user(): User | null {
    return this.session?.user ?? null;
  }

  get isSuperadmin(): boolean {
    return !!this.profile?.profile?.is_superadmin;
  }

  /**
   * The organization every project-scoped view is currently filtered to.
   * Backed by URL or explicit selection (#activeOrgIdOverride), and defaults
   * to `profile.default_organization_id` so it survives reloads.
   */
  get activeOrganizationId(): number | null {
    if (this.#activeOrgIdOverride != null) {
      if (!this.profile || this.isSuperadmin) return this.#activeOrgIdOverride;
      const orgs = this.profile.organizations ?? [];
      if (orgs.some((o) => o.organization_id === this.#activeOrgIdOverride)) {
        return this.#activeOrgIdOverride;
      }
    }
    const orgs = this.profile?.organizations ?? [];
    if (orgs.length === 0) return this.#activeOrgIdOverride;
    const saved = this.profile?.profile.default_organization_id;
    if (saved != null && orgs.some((o) => o.organization_id === saved)) return saved;
    return orgs.length === 1 ? orgs[0]!.organization_id : null;
  }

  get activeOrganization() {
    const id = this.activeOrganizationId;
    return this.profile?.organizations.find((o) => o.organization_id === id) ?? null;
  }

  /** True once signed in with more than one organization and none chosen yet. */
  get needsOrgSelection(): boolean {
    const orgs = this.profile?.organizations ?? [];
    return orgs.length > 1 && this.activeOrganizationId === null;
  }

  /** Set the caller's chosen organization, optionally persisting as their new default. */
  async setActiveOrganization(organizationId: number, persist: boolean = true): Promise<void> {
    this.#activeOrgIdOverride = organizationId;
    setActiveOrgId(organizationId);
    clearTenantCaches();
    if (persist && this.session) {
      await this.updateProfile({ default_organization_id: organizationId });
    }
  }

  constructor() {
    if (!isAuthConfigured) {
      this.loading = false;
      setAuthReady();
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      this.session = data.session;
      setAuthToken(data.session?.access_token ?? null);
      this.loading = false;
      this.#loadProfile();
      // Only the very first resolution marks readiness: it's the one a
      // request fired at page load could otherwise race. Later token
      // refreshes go through onAuthStateChange below and don't need to
      // gate anything -- callers awaiting authReady have long since moved on.
      setAuthReady();
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
      setActiveOrgId(null);
      clearTenantCaches();
      return;
    }
    try {
      this.profile = await authApi.me(this.session.access_token);
      setActiveOrgId(this.activeOrganizationId);
      clearTenantCaches();
    } catch {
      // Non-fatal: the header falls back to showing the Supabase user's
      // email, which is already on this.session.
      this.profile = null;
      setActiveOrgId(null);
    }
  }

  /** Merge fields into the caller's profile and refresh the cached copy. */
  async updateProfile(updates: ProfileUpdatePayload): Promise<void> {
    if (!this.session) return;
    const updated = await authApi.updateProfile(this.session.access_token, updates);
    if (this.profile) this.profile = { ...this.profile, profile: updated };
    setActiveOrgId(this.activeOrganizationId);
    clearTenantCaches();
  }

  /** Redirect to Google's consent screen; the browser comes back with a session. */
  async signInWithGoogle(): Promise<void> {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/` },
    });
    if (error) throw error;
  }

  /** Sign in with an existing email/password account. */
  async signInWithPassword(email: string, password: string): Promise<void> {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }

  /**
   * Create a new account with email and password. Accounts land in this
   * Supabase project's Auth > Users table, same as a Google sign-in.
   *
   * Whether the caller is signed in immediately depends on the project's
   * "Confirm email" setting: with it on (Supabase's default), `data.session`
   * comes back null and the caller must click the confirmation link emailed
   * to them before `signInWithPassword` will work; with it off, a session is
   * issued right away and `onAuthStateChange` picks it up like any other
   * sign-in. The returned flag tells the caller which case they're in so the
   * UI can show a "check your email" message rather than silently doing
   * nothing.
   */
  async signUp(email: string, password: string): Promise<{ needsEmailConfirmation: boolean }> {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/` },
    });
    if (error) throw error;
    return { needsEmailConfirmation: !data.session };
  }

  /**
   * Sign in with a seeded local dev account (see scripts/seed_dev_auth_user.py).
   * Goes through the real Supabase password grant -- same JWT, same backend
   * verification path as Google sign-in -- just without the OAuth round trip.
   * Only usable in dev builds with VITE_DEV_AUTH_EMAIL/PASSWORD set.
   */
  async signInWithDevAccount(): Promise<void> {
    const { error } = await supabase.auth.signInWithPassword({
      email: import.meta.env.VITE_DEV_AUTH_EMAIL as string,
      password: import.meta.env.VITE_DEV_AUTH_PASSWORD as string,
    });
    if (error) throw error;
  }

  async signOut(): Promise<void> {
    await supabase.auth.signOut();
    setAuthToken(null);
    this.#activeOrgIdOverride = null;
    setActiveOrgId(null);
    clearTenantCaches();
    this.profile = null;
  }
}

export const authState = new AuthState();
