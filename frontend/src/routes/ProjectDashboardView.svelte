<script lang="ts">
  import {
    Boxes,
    ScanEye,
    LayoutList,
    FileText,
    Activity,
    CheckCircle2,
  } from "lucide-svelte";
  import { modelsApi, projectsApi } from "../lib/api";
  import type { Project, Model } from "../lib/types";
  import { formatAnalysisDomain, viewForAnalysisDomain } from "../lib/analysisDomain";
  import PageHeader from "../lib/components/PageHeader.svelte";

  interface Props {
    initialProjectId: number | null;
    selectedProject?: Project | null;
    onNavigate: (view: string) => void;
  }

  let { initialProjectId, selectedProject = null, onNavigate }: Props = $props();

  let ifcFiles: Model[] = $state([]);
  let isLoadingFiles = $state(true);

  // See ModelsView.svelte for why this needs a token: App.svelte's
  // targetProjectId can briefly resolve to a stale project before its
  // URL-sync effect corrects it, and responses can arrive out of order.
  let loadToken = 0;
  // Guards against re-fetching a project this component already has (or
  // already has in flight): targetProjectId in App.svelte can bounce back to
  // a previously-seen id while the active organization is still settling
  // (see the profile-readiness comment on App.svelte's prefetch effect), and
  // without this, each bounce re-triggers this $effect and piles up another
  // modelsApi.list request on top of ones still in flight.
  let lastRequestedProjectId: number | null = null;

  async function loadFiles(projectId: number) {
    lastRequestedProjectId = projectId;
    const token = ++loadToken;
    isLoadingFiles = true;
    try {
      const result = await modelsApi.list(projectId);
      if (token !== loadToken) return;
      ifcFiles = result;
    } catch {
      if (token !== loadToken) return;
      ifcFiles = [];
    } finally {
      if (token === loadToken) isLoadingFiles = false;
    }
  }

  $effect(() => {
    if (initialProjectId && initialProjectId !== lastRequestedProjectId) {
      loadFiles(initialProjectId);
    }
  });

  let primaryFile = $derived(ifcFiles.find((f) => f.is_primary) || ifcFiles[0] || null);

  const AUDIT_ACTION = "audit";

  /**
   * The project's analysis domain, for choosing its audit tab.
   *
   * selectedProject can briefly name a different project than the one this
   * dashboard is for (see the stale-id note on loadToken above), so it is only
   * trusted when its id matches; otherwise the project is read by id. Any
   * failure yields null, which viewForAnalysisDomain maps to Architectural.
   */
  async function projectAnalysisDomain(): Promise<string | null> {
    if (selectedProject && selectedProject.id === initialProjectId) {
      return selectedProject.analysis_type ?? null;
    }
    if (!initialProjectId) return null;
    try {
      return (await projectsApi.get(initialProjectId)).analysis_type ?? null;
    } catch {
      return null;
    }
  }

  /**
   * Navigate for a quick-action card. Compliance Audit opens the Architectural,
   * Piping or Seismic tab matching the project's domain -- it used to hardcode
   * "arch", so every project landed on the Architectural tab.
   */
  async function openQuickAction(view: string) {
    if (view !== AUDIT_ACTION) {
      onNavigate(view);
      return;
    }
    onNavigate(viewForAnalysisDomain(await projectAnalysisDomain()));
  }

  const QUICK_ACTIONS = [
    {
      view: "models",
      label: "Models",
      description: "Attached IFC models — primary and context.",
      icon: Boxes,
      color: "blue",
    },
    {
      // Not a route: resolved on click to the audit tab for this project's
      // own domain (see openQuickAction).
      view: AUDIT_ACTION,
      label: "Compliance Audit",
      description: "Run architectural, piping or seismic checks.",
      icon: LayoutList,
      color: "emerald",
    },
    {
      view: "viewer",
      label: "3D Viewer",
      description: "Inspect geometry, properties and BCF viewpoints.",
      icon: ScanEye,
      color: "cyan",
    },
    {
      view: "reports",
      label: "Reports & Exports",
      description: "Compliance reports, BCF and CDE exports.",
      icon: FileText,
      color: "amber",
    },
    {
      view: "workflow",
      label: "Live Pipeline",
      description: "Track the current analysis run in real time.",
      icon: Activity,
      color: "purple",
    },
  ] as const;

  const COLOR_CLASSES: Record<string, string> = {
    blue: "bg-blue-500/10 text-blue-400 group-hover:text-blue-300",
    emerald: "bg-emerald-500/10 text-emerald-400 group-hover:text-emerald-300",
    cyan: "bg-cyan-500/10 text-cyan-400 group-hover:text-cyan-300",
    amber: "bg-amber-500/10 text-amber-400 group-hover:text-amber-300",
    purple: "bg-purple-500/10 text-purple-400 group-hover:text-purple-300",
  };
</script>

<div class="mx-auto space-y-8">
  <PageHeader
    category="Project"
    title={selectedProject?.name || "Project Dashboard"}
    subtitle={selectedProject?.description ||
      "Everything scoped to this project — models, compliance, and reports."}
  />

  <!-- Project info (not interactive -- plain metadata, no card/border) -->
  <div class="-mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs">
    <span>
      <span class="font-semibold uppercase tracking-wider text-fg-muted">Domain</span>
      <span class="ml-1.5 font-medium text-fg-secondary"
        >{selectedProject?.analysis_type
          ? formatAnalysisDomain(selectedProject.analysis_type)
          : "—"}</span
      >
    </span>
    <span class="text-border-default">·</span>
    <span>
      <span class="font-semibold uppercase tracking-wider text-fg-muted">Status</span>
      <span class="ml-1.5 font-medium text-fg-secondary">{selectedProject?.status || "—"}</span>
    </span>
  </div>

  <!-- Quick actions -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each QUICK_ACTIONS as action (action.view)}
      <button
        type="button"
        onclick={() => openQuickAction(action.view)}
        class="group rounded-2xl border border-border-default bg-surface-card/40 p-5 text-left transition-colors hover:border-border-interactive hover:bg-surface-hover"
      >
        <div
          class="mb-3 flex h-9 w-9 items-center justify-center rounded-xl transition-transform group-hover:scale-110 {COLOR_CLASSES[
            action.color
          ]}"
        >
          <action.icon class="h-4 w-4" />
        </div>
        <h3 class="text-sm font-semibold text-fg-primary transition-colors group-hover:text-accent">
          {action.label}
        </h3>
        <p class="mt-1 text-xs text-fg-muted">{action.description}</p>
        {#if action.view === "models"}
          <div class="mt-2.5 flex items-center gap-1.5 text-xs">
            <span class="font-semibold text-fg-primary">{isLoadingFiles ? "…" : ifcFiles.length}</span>
            <span class="text-fg-muted">attached</span>
          </div>
          {#if primaryFile}
            <div class="mt-1 flex items-center gap-1.5 truncate text-xs text-emerald-400">
              <CheckCircle2 class="h-3 w-3 shrink-0" />
              <span class="truncate">{primaryFile.file_name}</span>
            </div>
          {/if}
        {/if}
      </button>
    {/each}
  </div>
</div>
