<script lang="ts">
  import { push } from "svelte-spa-router";
  import { ShieldCheck, Mail, Lock } from "lucide-svelte";
  import { authState } from "../lib/auth.svelte";
  import { isAuthConfigured } from "../lib/supabaseClient";

  type Mode = "sign-in" | "sign-up";

  let mode = $state<Mode>("sign-in");
  let email = $state("");
  let password = $state("");
  let signingIn = $state(false);
  let error = $state<string | null>(null);
  let confirmationSent = $state(false);

  const devAuthConfigured =
    import.meta.env.DEV &&
    Boolean(import.meta.env.VITE_DEV_AUTH_EMAIL && import.meta.env.VITE_DEV_AUTH_PASSWORD);

  // Already signed in (or just finished the Google redirect) — nothing left
  // to do here.
  $effect(() => {
    if (authState.user) push("/");
  });

  function switchMode(next: Mode) {
    mode = next;
    error = null;
    confirmationSent = false;
  }

  async function handleGoogleSignIn() {
    signingIn = true;
    error = null;
    try {
      await authState.signInWithGoogle();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      signingIn = false;
    }
  }

  async function handleEmailSubmit(e: SubmitEvent) {
    e.preventDefault();
    signingIn = true;
    error = null;
    confirmationSent = false;
    try {
      if (mode === "sign-in") {
        await authState.signInWithPassword(email, password);
      } else {
        const { needsEmailConfirmation } = await authState.signUp(email, password);
        if (needsEmailConfirmation) {
          confirmationSent = true;
        }
        // Otherwise the project has email confirmation off: signUp already
        // issued a session, and the $effect above redirects once it lands.
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      signingIn = false;
    }
  }

  async function handleDevSignIn() {
    signingIn = true;
    error = null;
    try {
      await authState.signInWithDevAccount();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      signingIn = false;
    }
  }
</script>

<div class="flex min-h-[70vh] items-center justify-center">
  <div
    class="w-full max-w-sm space-y-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-center shadow-xl"
  >
    <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent">
      <ShieldCheck class="h-6 w-6" />
    </div>
    <div>
      <h1 class="text-lg font-semibold text-slate-100">
        {mode === "sign-in" ? "Sign in to BIM Guard" : "Create your BIM Guard account"}
      </h1>
      <p class="mt-1 text-xs text-slate-400">Continue with Google or your email.</p>
    </div>

    {#if !isAuthConfigured}
      <p class="rounded-lg border border-amber-800/60 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">
        Sign-in isn't configured in this environment. Set VITE_SUPABASE_URL and
        VITE_SUPABASE_ANON_KEY (see frontend/.env.example).
      </p>
    {/if}

    {#if error}
      <p class="rounded-lg border border-rose-800/60 bg-rose-950/40 px-3 py-2 text-xs text-rose-300">
        {error}
      </p>
    {/if}

    {#if confirmationSent}
      <p class="rounded-lg border border-emerald-800/60 bg-emerald-950/40 px-3 py-2 text-xs text-emerald-300">
        Check {email} for a confirmation link, then sign in.
      </p>
    {/if}

    <button
      type="button"
      onclick={handleGoogleSignIn}
      disabled={signingIn || !isAuthConfigured}
      class="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-100 transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <svg class="h-4 w-4" viewBox="0 0 48 48" aria-hidden="true">
        <path
          fill="#FFC107"
          d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.3 35.5 24 35.5c-6.4 0-11.7-3.9-13.6-9.2A12.2 12.2 0 0 1 10 24c0-.8.1-1.6.2-2.3C11.9 16.4 17.3 12.5 24 12.5c3.1 0 6 1.1 8.2 3l6-6C34.6 6 29.6 4 24 4 13 4 4 13 4 24s9 20 20 20c11 0 20-9 20-20 0-1.2-.1-2.3-.4-3.5z"
        />
        <path
          fill="#FF3D00"
          d="m6.3 14.7 6.6 4.8C14.6 15.6 18.9 12.5 24 12.5c3.1 0 6 1.1 8.2 3l6-6C34.6 6 29.6 4 24 4c-7.9 0-14.6 4.4-17.7 10.7z"
        />
        <path
          fill="#4CAF50"
          d="M24 44c5.5 0 10.4-1.9 14.2-5.1l-6.6-5.4C29.5 35.1 26.9 36 24 36c-5.3 0-9.7-3.1-11.3-7.5l-6.5 5C9.3 39.6 16.1 44 24 44z"
        />
        <path
          fill="#1976D2"
          d="M43.6 20.5H42V20H24v8h11.3a12.4 12.4 0 0 1-4.3 5.9l6.6 5.4C41.5 36 44 30.5 44 24c0-1.2-.1-2.3-.4-3.5z"
        />
      </svg>
      {signingIn ? "Redirecting…" : "Continue with Google"}
    </button>

    <div class="flex items-center gap-3 text-micro font-medium uppercase tracking-wider text-slate-500">
      <span class="h-px flex-1 bg-slate-800"></span>
      <span>or</span>
      <span class="h-px flex-1 bg-slate-800"></span>
    </div>

    <form class="space-y-3 text-left" onsubmit={handleEmailSubmit}>
      <div class="space-y-1">
        <label for="login-email" class="text-caption font-medium text-slate-400">Email</label>
        <div class="relative">
          <Mail class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            id="login-email"
            type="email"
            required
            autocomplete="email"
            bind:value={email}
            disabled={signingIn || !isAuthConfigured}
            class="w-full rounded-xl border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-500 focus:border-accent focus:outline-none disabled:opacity-60"
            placeholder="you@company.com"
          />
        </div>
      </div>

      <div class="space-y-1">
        <label for="login-password" class="text-caption font-medium text-slate-400">Password</label>
        <div class="relative">
          <Lock class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            id="login-password"
            type="password"
            required
            minlength="6"
            autocomplete={mode === "sign-in" ? "current-password" : "new-password"}
            bind:value={password}
            disabled={signingIn || !isAuthConfigured}
            class="w-full rounded-xl border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm text-slate-100 placeholder-slate-500 focus:border-accent focus:outline-none disabled:opacity-60"
            placeholder="••••••••"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={signingIn || !isAuthConfigured}
        class="w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
      >
        {#if signingIn}
          {mode === "sign-in" ? "Signing in…" : "Creating account…"}
        {:else}
          {mode === "sign-in" ? "Sign in" : "Create account"}
        {/if}
      </button>
    </form>

    <p class="text-xs text-slate-400">
      {#if mode === "sign-in"}
        Don't have an account?
        <button
          type="button"
          onclick={() => switchMode("sign-up")}
          class="font-semibold text-accent hover:underline"
        >
          Sign up
        </button>
      {:else}
        Already have an account?
        <button
          type="button"
          onclick={() => switchMode("sign-in")}
          class="font-semibold text-accent hover:underline"
        >
          Sign in
        </button>
      {/if}
    </p>

    {#if devAuthConfigured}
      <button
        type="button"
        onclick={handleDevSignIn}
        disabled={signingIn}
        class="w-full rounded-xl border border-dashed border-amber-700/60 bg-transparent px-4 py-2 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-950/30 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Sign in as dev test user
      </button>
    {/if}
  </div>
</div>
