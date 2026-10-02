<script lang="ts">
  import { link, push } from "svelte-spa-router";
  import { ShieldCheck, Mail, Lock, CheckCircle2, Sparkles, Building2 } from "lucide-svelte";
  import { authState } from "../lib/auth.svelte";
  import { isAuthConfigured } from "../lib/supabaseClient";
  import { Button, Input } from "../lib/components/ui";

  type Mode = "sign-in" | "sign-up";

  let mode = $state<Mode>("sign-in");
  let email = $state("");
  let password = $state("");
  let signingIn = $state(false);
  let error = $state<string | null>(null);
  let confirmationSent = $state(false);

  const devAuthConfigured =
    (import.meta.env.DEV || import.meta.env.VITE_ALLOW_DEV_LOGIN === "true") &&
    Boolean(import.meta.env.VITE_DEV_AUTH_EMAIL && import.meta.env.VITE_DEV_AUTH_PASSWORD);

  // Already signed in (or just finished the Google redirect) — nothing left to do here.
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

<div class="grid min-h-screen w-full lg:grid-cols-2">
  <!-- Left Column: Form & Actions (login-03) -->
  <div class="flex flex-col justify-between p-6 sm:p-10 md:p-12">
    <!-- Brand Header -->
    <div class="flex items-center justify-between">
      <a href="/" use:link class="flex items-center gap-2.5 outline-hidden group">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-xl bg-linear-to-tr from-accent to-cyan-400 font-bold text-white shadow-md shadow-blue-500/20 transition-transform group-hover:scale-105"
        >
          BG
        </div>
        <div class="flex flex-col">
          <span class="text-base font-bold leading-none tracking-tight text-fg-primary"
            >BIM Guard</span
          >
          <span class="text-nano font-semibold uppercase tracking-widest text-fg-muted mt-0.5"
            >OpenBIM Compliance</span
          >
        </div>
      </a>

      <a
        href="/"
        use:link
        class="text-xs font-medium text-fg-muted hover:text-fg-primary transition-colors hidden sm:inline-block"
      >
        &larr; Back to overview
      </a>
    </div>

    <!-- Center: Form Card -->
    <div class="mx-auto flex w-full max-w-sm flex-col justify-center py-10">
      <div class="mb-6 space-y-1.5 text-left">
        <h1 class="text-2xl font-bold tracking-tight text-fg-primary">
          {mode === "sign-in" ? "Welcome back" : "Create an account"}
        </h1>
        <p class="text-xs text-fg-muted">
          {mode === "sign-in"
            ? "Enter your credentials to access your organization workspace"
            : "Sign up to begin automating OpenBIM architectural compliance"}
        </p>
      </div>

      {#if !isAuthConfigured}
        <div class="mb-4 rounded-xl border border-warning-border bg-warning-bg/60 p-3 text-xs text-warning">
          Sign-in is not configured in this environment. Please configure Supabase variables in your <code class="font-mono text-nano bg-surface-overlay px-1 py-0.5 rounded">.env</code>.
        </div>
      {/if}

      {#if error}
        <div class="mb-4 rounded-xl border border-critical-border bg-critical-bg p-3 text-xs text-critical">
          {error}
        </div>
      {/if}

      {#if confirmationSent}
        <div class="mb-4 rounded-xl border border-success-border bg-success-bg/40 p-3 text-xs text-success">
          Confirmation link sent to <span class="font-semibold">{email}</span>. Please verify to sign in.
        </div>
      {/if}

      <!-- Google OAuth Action -->
      <Button
        variant="secondary"
        size="lg"
        disabled={signingIn || !isAuthConfigured}
        onclick={handleGoogleSignIn}
        class="w-full gap-2.5 font-medium"
      >
        <svg class="h-4 w-4 shrink-0" viewBox="0 0 48 48" aria-hidden="true">
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
        <span>{signingIn ? "Redirecting…" : "Continue with Google"}</span>
      </Button>

      <!-- Divider -->
      <div class="relative my-5 text-center text-xs after:absolute after:inset-0 after:top-1/2 after:z-0 after:flex after:items-center after:border-t after:border-border-default/60">
        <span class="relative z-10 bg-surface-canvas px-2 text-nano font-semibold uppercase tracking-wider text-fg-muted">
          Or continue with email
        </span>
      </div>

      <!-- Email/Password Form -->
      <form class="space-y-4" onsubmit={handleEmailSubmit}>
        <div class="space-y-1.5 text-left">
          <label for="login-email" class="text-caption font-medium text-fg-secondary">Email</label>
          <Input
            id="login-email"
            type="email"
            required
            autocomplete="email"
            bind:value={email}
            disabled={signingIn || !isAuthConfigured}
            placeholder="architect@domain.com"
          >
            {#snippet prefixIcon()}
              <Mail class="h-3.5 w-3.5" />
            {/snippet}
          </Input>
        </div>

        <div class="space-y-1.5 text-left">
          <div class="flex items-center justify-between">
            <label for="login-password" class="text-caption font-medium text-fg-secondary">Password</label>
            {#if mode === "sign-in"}
              <span class="text-nano text-fg-muted">Min. 6 characters</span>
            {/if}
          </div>
          <Input
            id="login-password"
            type="password"
            required
            minlength={6}
            autocomplete={mode === "sign-in" ? "current-password" : "new-password"}
            bind:value={password}
            disabled={signingIn || !isAuthConfigured}
            placeholder="••••••••"
          >
            {#snippet prefixIcon()}
              <Lock class="h-3.5 w-3.5" />
            {/snippet}
          </Input>
        </div>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={signingIn}
          disabled={signingIn || !isAuthConfigured}
          class="w-full font-semibold shadow-md shadow-blue-500/10"
        >
          {mode === "sign-in" ? "Sign in" : "Create account"}
        </Button>
      </form>

      <!-- Switch Sign-in / Sign-up Mode -->
      <div class="mt-4 text-center text-xs text-fg-muted">
        {#if mode === "sign-in"}
          Don't have an account?
          <button
            type="button"
            onclick={() => switchMode("sign-up")}
            class="font-semibold text-accent hover:underline ml-1 cursor-pointer"
          >
            Sign up
          </button>
        {:else}
          Already have an account?
          <button
            type="button"
            onclick={() => switchMode("sign-in")}
            class="font-semibold text-accent hover:underline ml-1 cursor-pointer"
          >
            Sign in
          </button>
        {/if}
      </div>

      <!-- Dev Auth Bypass (Local development only) -->
      {#if devAuthConfigured}
        <div class="mt-4 pt-3 border-t border-border-default/40">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onclick={handleDevSignIn}
            disabled={signingIn}
            class="w-full border-dashed border-warning-border/70 text-warning hover:bg-warning-bg/30 text-nano font-medium"
          >
            Sign in as dev test user
          </Button>
        </div>
      {/if}
    </div>

    <!-- Bottom Disclaimer -->
    <div class="text-center text-nano text-fg-muted">
      By signing in, you agree to our
      <a href="/terms" use:link class="text-fg-secondary underline underline-offset-2 hover:text-accent transition-colors"
        >Terms of Service</a
      >
      and
      <a href="/privacy" use:link class="text-fg-secondary underline underline-offset-2 hover:text-accent transition-colors"
        >Privacy Policy</a
      >.
    </div>
  </div>

  <!-- Right Column: Visual Showcase (login-03) -->
  <div
    class="relative hidden lg:flex flex-col justify-between border-l border-border-default bg-surface-card p-10 overflow-hidden"
  >
    <!-- Background Gradient Accent Glow -->
    <div
      class="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-accent/15 blur-3xl"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute -bottom-24 -left-24 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl"
      aria-hidden="true"
    ></div>

    <!-- Subtle Technical Grid Lines -->
    <div
      class="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px]"
      aria-hidden="true"
    ></div>

    <!-- Top Badge -->
    <div class="relative z-10 flex items-center justify-between">
      <div class="inline-flex items-center gap-2 rounded-full border border-border-default bg-surface-overlay/80 px-3 py-1 text-xs font-semibold text-fg-secondary backdrop-blur-md">
        <Sparkles class="h-3.5 w-3.5 text-accent" />
        <span>ISO 19650 & OpenBIM Automated Audit</span>
      </div>
      <span class="text-nano font-mono text-fg-muted tracking-wider uppercase">Engine v2.4</span>
    </div>

    <!-- Middle: Live Compliance Evaluation Simulation Card -->
    <div class="relative z-10 my-auto py-8">
      <div
        class="apple-blur mx-auto max-w-md rounded-2xl border border-border-default/80 bg-surface-card/90 p-6 shadow-2xl shadow-black/20"
      >
        <div class="flex items-center justify-between border-b border-border-default/50 pb-3">
          <div class="flex items-center gap-2.5">
            <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <Building2 class="h-4 w-4" />
            </div>
            <div>
              <div class="text-xs font-bold text-fg-primary">Auditorium Model L02</div>
              <div class="text-nano font-mono text-fg-muted">ARCH-MODEL-004 · IFC4</div>
            </div>
          </div>
          <span class="rounded-full bg-success-bg px-2 py-0.5 text-nano font-semibold text-success border border-success-border">
            100% Compliant
          </span>
        </div>

        <div class="mt-4 space-y-3">
          <!-- Check 1 -->
          <div class="flex items-center justify-between rounded-xl bg-surface-overlay/50 p-2.5 text-xs">
            <div class="flex items-center gap-2">
              <CheckCircle2 class="h-4 w-4 text-success shrink-0" />
              <div>
                <div class="font-medium text-fg-primary">ARCH-EGRESS-001</div>
                <div class="text-nano text-fg-muted">Clear door width ≥ 850mm</div>
              </div>
            </div>
            <span class="font-mono text-nano font-semibold text-success">920mm (Pass)</span>
          </div>

          <!-- Check 2 -->
          <div class="flex items-center justify-between rounded-xl bg-surface-overlay/50 p-2.5 text-xs">
            <div class="flex items-center gap-2">
              <CheckCircle2 class="h-4 w-4 text-success shrink-0" />
              <div>
                <div class="font-medium text-fg-primary">ARCH-SPATIAL-001</div>
                <div class="text-nano text-fg-muted">Corridor headroom ≥ 2100mm</div>
              </div>
            </div>
            <span class="font-mono text-nano font-semibold text-success">2450mm (Pass)</span>
          </div>

          <!-- Check 3 -->
          <div class="flex items-center justify-between rounded-xl bg-surface-overlay/50 p-2.5 text-xs">
            <div class="flex items-center gap-2">
              <CheckCircle2 class="h-4 w-4 text-success shrink-0" />
              <div>
                <div class="font-medium text-fg-primary">ISO 19650 Governance</div>
                <div class="text-nano text-fg-muted">State: SHARED · Rev: P02</div>
              </div>
            </div>
            <span class="font-mono text-nano font-semibold text-accent">Verified</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Testimonial / Value Statement -->
    <div class="relative z-10 space-y-2">
      <blockquote class="text-sm font-medium leading-relaxed text-fg-secondary">
        “BIM Guard transforms static building specifications into deterministic compliance pipelines — ensuring architectural models meet every standard before construction begins.”
      </blockquote>
      <div class="text-xs font-semibold text-fg-muted">
        BIM Guard Engineering Architecture
      </div>
    </div>
  </div>
</div>
