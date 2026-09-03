<script lang="ts">
  import { ExternalLink, Activity, Menu } from "lucide-svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import type { Project } from "../types";

  export let activeView: string;
  export let selectedProject: Project | null = null;
  export let apiOnline: boolean = true;
  export let dbOk: boolean = true;
  export let dbBackend: string = "SUPABASE";
  /** Opens the navigation drawer; only rendered below `md`. */
  export let onOpenMobileNav: () => void = () => {};

  const TITLES: Record<string, { section: string; title: string }> = {
    dashboard: { section: "Platform", title: "Compliance Dashboard" },
    projects: { section: "Platform", title: "Project Registry" },
    viewer: { section: "Platform", title: "3D OpenBIM Viewer" },
    documents: { section: "Library", title: "Document Specifications" },
    extract: { section: "Library", title: "Rule Extraction Studio" },
    rules: { section: "Library", title: "Rules Catalog" },
    "manual-rule-editor": { section: "Library", title: "Manual Rule Editor" },
    arch: { section: "Analysis", title: "Architectural Compliance Audit" },
    piping: { section: "Analysis", title: "Piping Corrosion Audit" },
    seismic: { section: "Analysis", title: "Seismic Clearance Audit" },
    analyze: { section: "Analysis", title: "MEP Piping & Seismic Audit" },
    workflow: { section: "Analysis", title: "Live Pipeline Tracker" },
    reports: { section: "Analysis", title: "Compliance Reports & Exports" },
    "user-manual": { section: "Manuals", title: "User Workflow Manual" },
    "modeling-manual": { section: "Manuals", title: "3D Modeling Reference" },
    settings: { section: "System", title: "Application Settings" },
  };

  $: headerInfo = TITLES[activeView] || {
    section: "BIM Guard",
    title: activeView,
  };
</script>

<header
  class="h-16 border-b border-slate-800 bg-slate-950/60 apple-blur sticky top-0 z-30 px-4 md:px-6 flex items-center justify-between gap-2"
>
  <!-- Breadcrumb -->
  <div class="flex items-center gap-2 text-sm min-w-0">
    <button
      type="button"
      on:click={onOpenMobileNav}
      class="-ml-1 p-2 rounded-lg text-slate-400 hover:text-slate-50 hover:bg-slate-900 transition-colors md:hidden"
      aria-label="Open navigation"
      aria-controls="app-sidebar"
    >
      <Menu class="w-5 h-5" />
    </button>
    <span class="text-slate-500 font-medium hidden sm:inline">{headerInfo.section}</span>
    <span class="text-slate-600 hidden sm:inline">/</span>
    <span class="font-semibold text-slate-100 truncate">{headerInfo.title}</span>

    {#if selectedProject}
      <span
        class="ml-2 hidden lg:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20"
      >
        Project: {selectedProject.name}
      </span>
    {/if}
  </div>

  <!-- Actions & Status -->
  <div class="flex items-center gap-2.5 shrink-0">
    <!-- Compact combined health dot for narrow viewports -->
    <span
      class="lg:hidden inline-flex items-center justify-center w-7 h-7 rounded-full border {apiOnline && dbOk
        ? 'bg-emerald-950/40 border-emerald-800/60'
        : 'bg-rose-950/40 border-rose-800/60'}"
      title={`Gateway ${apiOnline ? 'active' : 'offline'} - DB ${dbBackend} ${dbOk ? 'connected' : 'degraded'}`}
    >
      <span
        class="w-1.5 h-1.5 rounded-full {apiOnline && dbOk ? 'bg-emerald-400' : 'bg-rose-400'}"
      ></span>
      <span class="sr-only"
        >Gateway {apiOnline ? "active" : "offline"}, database {dbOk ? "connected" : "degraded"}</span
      >
    </span>

    <!-- Health status -->
    <span
      class="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border {apiOnline
        ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
        : 'bg-rose-950/40 text-rose-400 border-rose-800/60'}"
    >
      <span
        class="w-1.5 h-1.5 rounded-full {apiOnline
          ? 'bg-emerald-400'
          : 'bg-rose-400'}"
      ></span>
      {apiOnline ? "FastAPI Gateway Active" : "Gateway Offline"}
    </span>

    <!-- DB Status indicator -->
    <span
      class="hidden lg:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border {dbOk
        ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
        : 'bg-rose-950/40 text-rose-400 border-rose-800/60'}"
    >
      <span
        class="w-1.5 h-1.5 rounded-full {dbOk
          ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50'
          : 'bg-rose-400'}"
      ></span>
      DB {dbBackend}: {dbOk ? "Connected" : "Degraded"}
    </span>

    <a
      href="/api/docs"
      target="_blank"
      rel="noopener noreferrer"
      class="text-xs text-slate-400 hover:text-slate-50 px-2.5 py-1 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/60 hidden md:flex items-center gap-1 transition-colors"
      title="Open Swagger OpenAPI Documentation"
    >
      <span>API Docs</span>
      <ExternalLink class="w-3 h-3" />
    </a>

    <!-- Theme Toggle Button -->
    <ThemeToggle />

  </div>
</header>
