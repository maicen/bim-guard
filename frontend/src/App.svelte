<script lang="ts">
  import { onMount } from "svelte";
  import { router, push } from "svelte-spa-router";
  import Toaster from "./lib/components/Toaster.svelte";
  import OfflineBanner from "./lib/components/OfflineBanner.svelte";
  import LazyView from "./lib/components/LazyView.svelte";
  import LoginView from "./routes/LoginView.svelte";
  import LandingView from "./routes/LandingView.svelte";
  import { initTheme } from "./lib/theme";
  import { authState } from "./lib/auth.svelte";
  import { isAuthConfigured, sessionPossible } from "./lib/authConfig";

  // PERF (mobile PageSpeed): this file is deliberately thin. The signed-in app
  // shell (sidebars, header, bits-ui tooltips/dialogs, pipeline tracker,
  // every route table) lives in AppShell.svelte and is fetched only when a
  // session is possible. Before the split, the landing page -- the only page
  // a search/AI crawler or first-time visitor ever sees -- shipped the whole
  // shell in the entry chunk (~200 KiB gzip, 60% unused on "/"), and mounted
  // the shell's "Loading your session..." skeleton until Supabase answered,
  // so the hero <h1> (the LCP element) painted ~2.7 s late on a throttled
  // phone. Keep new shell-only imports in AppShell.svelte, not here.

  // Whether a session *could* exist, decided synchronously at load (see
  // sessionPossible in authConfig.ts). With none, getSession() can only resolve
  // to "signed out", so the landing page paints now instead of after that round trip.
  const mayBeSignedIn = sessionPossible();

  let activeView = $derived(router.location === "/" ? "dashboard" : router.location.slice(1));

  // Same contract as before the split: signed out, only "/" (landing) and
  // "/login" are reachable; any other deep link falls back to the landing page.
  let showShell = $derived(
    !isAuthConfigured || !!authState.user || (authState.loading && mayBeSignedIn),
  );
  let signedOutRedirect = $derived(
    isAuthConfigured && !showShell && activeView !== "login" && activeView !== "dashboard",
  );
  $effect(() => {
    if (signedOutRedirect) push("/");
  });

  onMount(() => {
    initTheme();

    // Expose the main actions to in-browser AI agents (WebMCP). Feature-detect
    // first so browsers without it never download the tool definitions.
    const hasWebMcp =
      (document as unknown as { modelContext?: unknown }).modelContext ??
      (navigator as unknown as { modelContext?: unknown }).modelContext;
    let cleanup = () => {};
    let disposed = false;
    if (hasWebMcp) {
      void import("./lib/webmcp").then((m) => {
        if (disposed) return;
        cleanup = m.registerWebMcpTools();
      });
    }
    return () => {
      disposed = true;
      cleanup();
    };
  });
</script>

{#if showShell}
  <LazyView loader={() => import("./AppShell.svelte")} />
{:else}
  <a
    href="#main-content"
    class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-200 focus:rounded-xl focus:bg-accent focus:px-4 focus:py-2 focus:text-xs focus:font-semibold focus:text-white"
  >
    Skip to main content
  </a>
  <!-- Signed out: the landing page and sign-in screen are full-bleed, with
       none of the working app's sidebar/header chrome around them. -->
  <div class="min-h-screen bg-surface-canvas font-sans text-fg-primary antialiased">
    {#if activeView === "login"}
      <main id="main-content" tabindex="-1">
        <LoginView />
      </main>
    {:else}
      <LandingView />
    {/if}
  </div>
{/if}

<Toaster />
<OfflineBanner />
