<script lang="ts">
  import { ExternalLink, Activity, Menu } from "lucide-svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import GlobalPipelineStatus from "./GlobalPipelineStatus.svelte";
  import ProjectSwitcher from "./ProjectSwitcher.svelte";
  import UserMenu from "./UserMenu.svelte";
  import type { Project } from "../types";

  interface Props {
    activeView: string;
    selectedProject?: Project | null;
    apiOnline?: boolean;
    dbOk?: boolean;
    dbBackend?: string;
    /** Opens the navigation drawer; only rendered below `md`. */
    onOpenMobileNav?: () => void;
    /** Navigate to the Live Workflow view for a tracked project's pipeline. */
    onOpenPipeline?: (projectId: number) => void;
    /** Switch the app's current project context. */
    onSwitchProject?: (projectId: number) => void;
  }

  let {
    activeView,
    selectedProject = null,
    apiOnline = true,
    dbOk = true,
    dbBackend = "SUPABASE",
    onOpenMobileNav = () => {},
    onOpenPipeline,
    onSwitchProject,
  }: Props = $props();

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
    "revit-sync": { section: "Integrations", title: "Autodesk Revit Direct Sync" },
    "ifc-export-setting": { section: "Integrations", title: "IFC Export Setting" },
    "user-manual": { section: "Manuals", title: "User Workflow Manual" },
    "modeling-manual": { section: "Manuals", title: "3D Modeling Reference" },
    settings: { section: "System", title: "Application Settings" },
  };

  let headerInfo = $derived(
    TITLES[activeView] || {
      section: "BIM Guard",
      title: activeView,
    },
  );
</script>

<header
  class="apple-blur sticky top-0 z-30 flex h-16 items-center justify-between gap-2 border-b border-slate-800 bg-slate-950/60 px-4 md:px-6"
>
  <!-- Breadcrumb -->
  <div class="flex min-w-0 items-center gap-2 text-sm">
    <button
      type="button"
      onclick={onOpenMobileNav}
      class="-ml-1 rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-900 hover:text-slate-50 md:hidden"
      aria-label="Open navigation"
      aria-controls="app-sidebar"
    >
      <Menu class="h-5 w-5" />
    </button>
    <span class="hidden font-medium text-slate-500 sm:inline">{headerInfo.section}</span>
    <span class="hidden text-slate-600 sm:inline">/</span>
    <span class="truncate font-semibold text-slate-100">{headerInfo.title}</span>

    {#if onSwitchProject}
      <ProjectSwitcher {selectedProject} onSwitch={onSwitchProject} />
    {:else if selectedProject}
      <span
        class="ml-2 hidden items-center gap-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-400 lg:inline-flex"
      >
        Project: {selectedProject.name}
      </span>
    {/if}
  </div>

  <!-- Actions & Status -->
  <div class="flex shrink-0 items-center gap-2.5">
    <GlobalPipelineStatus onOpen={onOpenPipeline} />

    <!-- Compact combined health dot for narrow viewports -->
    <span
      class="inline-flex h-7 w-7 items-center justify-center rounded-full border lg:hidden {apiOnline &&
      dbOk
        ? 'border-emerald-800/60 bg-emerald-950/40'
        : 'border-rose-800/60 bg-rose-950/40'}"
      title={`Gateway ${apiOnline ? "active" : "offline"} - DB ${dbBackend} ${dbOk ? "connected" : "degraded"}`}
    >
      <span class="h-1.5 w-1.5 rounded-full {apiOnline && dbOk ? 'bg-emerald-400' : 'bg-rose-400'}"
      ></span>
      <span class="sr-only"
        >Gateway {apiOnline ? "active" : "offline"}, database {dbOk
          ? "connected"
          : "degraded"}</span
      >
    </span>

    <!-- Health status -->
    <span
      class="hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium lg:inline-flex {apiOnline
        ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-400'
        : 'border-rose-800/60 bg-rose-950/40 text-rose-400'}"
    >
      <span class="h-1.5 w-1.5 rounded-full {apiOnline ? 'bg-emerald-400' : 'bg-rose-400'}"></span>
      {apiOnline ? "FastAPI Gateway Active" : "Gateway Offline"}
    </span>

    <!-- DB Status indicator -->
    <span
      class="hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium lg:inline-flex {dbOk
        ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-400'
        : 'border-rose-800/60 bg-rose-950/40 text-rose-400'}"
    >
      <span
        class="h-1.5 w-1.5 rounded-full {dbOk
          ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50'
          : 'bg-rose-400'}"
      ></span>
      DB {dbBackend}: {dbOk ? "Connected" : "Degraded"}
    </span>

    <a
      href="/api/docs"
      target="_blank"
      rel="noopener noreferrer"
      class="hidden items-center gap-1 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-xs text-slate-400 transition-colors hover:border-slate-700 hover:text-slate-50 md:flex"
      title="Open Swagger OpenAPI Documentation"
    >
      <span>API Docs</span>
      <ExternalLink class="h-3 w-3" />
    </a>

    <!-- Theme Toggle Button -->
    <ThemeToggle />

    <UserMenu />
  </div>
</header>
