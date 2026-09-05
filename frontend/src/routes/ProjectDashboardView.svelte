<script lang="ts">
  import { onMount } from "svelte";
  import {
    Boxes,
    ScanEye,
    LayoutList,
    FileText,
    Activity,
    CheckCircle2,
    ArrowRight,
  } from "lucide-svelte";
  import { projectsApi } from "../lib/api";
  import type { Project, ProjectIfcFile } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";

  interface Props {
    initialProjectId: number | null;
    selectedProject?: Project | null;
    onNavigate: (view: string) => void;
  }

  let { initialProjectId, selectedProject = null, onNavigate }: Props = $props();

  let ifcFiles: ProjectIfcFile[] = $state([]);
  let isLoadingFiles = $state(true);

  async function loadFiles(projectId: number) {
    isLoadingFiles = true;
    try {
      ifcFiles = await projectsApi.listIfcFiles(projectId);
    } catch {
      ifcFiles = [];
    } finally {
      isLoadingFiles = false;
    }
  }

  onMount(() => {
    if (initialProjectId) loadFiles(initialProjectId);
  });

  $effect(() => {
    if (initialProjectId) loadFiles(initialProjectId);
  });

  let primaryFile = $derived(ifcFiles.find((f) => f.is_primary) || ifcFiles[0] || null);

  const QUICK_ACTIONS = [
    {
      view: "models",
      label: "Models",
      description: "Attached IFC models — primary and context.",
      icon: Boxes,
      color: "blue",
    },
    {
      view: "arch",
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

  <!-- Project summary card -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
    <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div class="text-xs font-semibold uppercase tracking-wider text-slate-400">Domain</div>
      <div class="mt-2 text-xl font-bold text-slate-50">
        {selectedProject?.analysis_type || "—"}
      </div>
    </div>
    <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div class="text-xs font-semibold uppercase tracking-wider text-slate-400">Status</div>
      <div class="mt-2 text-xl font-bold text-slate-50">{selectedProject?.status || "—"}</div>
    </div>
    <button
      type="button"
      onclick={() => onNavigate("models")}
      class="group rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-left transition-all hover:border-slate-700"
    >
      <div class="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400">
        <span>Models</span>
        <ArrowRight class="h-3.5 w-3.5 text-blue-400 opacity-0 transition-all group-hover:opacity-100" />
      </div>
      <div class="mt-2 flex items-center gap-2 text-xl font-bold text-slate-50">
        {isLoadingFiles ? "…" : ifcFiles.length}
        <span class="text-xs font-normal text-slate-400">attached</span>
      </div>
      {#if primaryFile}
        <div class="mt-1 flex items-center gap-1.5 truncate text-xs text-emerald-400">
          <CheckCircle2 class="h-3 w-3 shrink-0" />
          <span class="truncate">{primaryFile.file_name}</span>
        </div>
      {/if}
    </button>
  </div>

  <!-- Quick actions -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each QUICK_ACTIONS as action (action.view)}
      <button
        type="button"
        onclick={() => onNavigate(action.view)}
        class="group rounded-2xl border border-slate-800 bg-slate-900/40 p-5 text-left transition-all hover:border-slate-700"
      >
        <div
          class="mb-3 flex h-9 w-9 items-center justify-center rounded-xl transition-transform group-hover:scale-110 {COLOR_CLASSES[
            action.color
          ]}"
        >
          <action.icon class="h-4 w-4" />
        </div>
        <h3 class="text-sm font-semibold text-slate-50">{action.label}</h3>
        <p class="mt-1 text-xs text-slate-400">{action.description}</p>
      </button>
    {/each}
  </div>
</div>
