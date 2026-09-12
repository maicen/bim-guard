<script lang="ts">
  import { push } from "svelte-spa-router";
  import {
    ShieldCheck,
    ScanEye,
    GitBranch,
    Workflow,
    Building2,
    ArrowRight,
  } from "lucide-svelte";

  const FEATURES = [
    {
      icon: ScanEye,
      title: "3D-native compliance",
      body: "Every flagged clearance or corrosion risk (GC-001, CC-001, MC-001) is isolated directly in your IFC model — no separate report to cross-reference.",
    },
    {
      icon: Workflow,
      title: "ISO 19650 governance built in",
      body: "Projects carry real CDE metadata — suitability, revision, WIP → SHARED → PUBLISHED → ARCHIVED — enforced by a state machine, not a spreadsheet convention.",
    },
    {
      icon: GitBranch,
      title: "BCF-native coordination",
      body: "Coordination issues route as standard BCF topics, so they land in the same tools your consultants and subcontractors already use.",
    },
    {
      icon: Building2,
      title: "Built for multi-tenant teams",
      body: "Organizations, roles, and project scoping are first-class — the same account works across every client and project you run.",
    },
  ];
</script>

<div class="min-h-screen bg-surface-canvas font-sans text-fg-primary antialiased">
  <header class="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
    <div class="flex items-center gap-2.5">
      <div
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-linear-to-tr from-accent to-cyan-400 text-sm font-bold text-white shadow-md shadow-blue-500/20"
      >
        BG
      </div>
      <span class="text-base font-bold tracking-tight text-fg-primary">BIM Guard</span>
    </div>
    <button
      type="button"
      onclick={() => push("/login")}
      class="rounded-lg border border-border-default bg-surface-card/60 px-4 py-1.5 text-xs font-semibold text-fg-secondary transition-colors hover:border-border-interactive hover:bg-surface-hover"
    >
      Sign in
    </button>
  </header>

  <main>
    <!-- Hero -->
    <section class="mx-auto max-w-4xl px-6 pb-16 pt-10 text-center sm:pb-20 sm:pt-16">
      <div
        class="mx-auto mb-6 inline-flex items-center gap-1.5 rounded-md border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent"
      >
        <ShieldCheck class="h-3.5 w-3.5" />
        OpenBIM Compliance Engine
      </div>
      <h1 class="text-3xl font-bold leading-tight tracking-tight text-fg-primary sm:text-5xl">
        Automated code compliance for the models you already have.
      </h1>
      <p class="mx-auto mt-5 max-w-2xl text-sm leading-relaxed text-fg-muted sm:text-base">
        BIM Guard reads your IFC models directly, runs galvanic, crevice, and
        microbiological corrosion checks alongside architectural code rules, and
        routes every finding as a BCF issue your team can act on — without
        leaving your model.
      </p>
      <div class="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onclick={() => push("/login")}
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-950/50 transition-all hover:scale-[1.02] hover:bg-accent-hover"
        >
          Get started
          <ArrowRight class="h-4 w-4" />
        </button>
      </div>
    </section>

    <!-- Feature grid -->
    <section class="mx-auto max-w-6xl px-6 pb-24">
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {#each FEATURES as feature (feature.title)}
          <div class="rounded-2xl border border-border-default bg-surface-card/40 p-5">
            <div
              class="mb-3 flex h-9 w-9 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent"
            >
              <feature.icon class="h-4 w-4" />
            </div>
            <h3 class="text-sm font-bold text-fg-primary">{feature.title}</h3>
            <p class="mt-1.5 text-xs leading-relaxed text-fg-muted">{feature.body}</p>
          </div>
        {/each}
      </div>
    </section>
  </main>

  <footer
    class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 border-t border-border-default px-6 py-6 text-xs text-fg-muted"
  >
    <span>BIM Guard OpenBIM Compliance Engine</span>
    <span>&copy; {new Date().getFullYear()} BIM Guard</span>
  </footer>
</div>
