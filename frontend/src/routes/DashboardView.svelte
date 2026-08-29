<script lang="ts">
  import { onMount } from "svelte";
  import {
    FolderOpen,
    BookOpen,
    ListChecks,
    AlertTriangle,
    Plus,
    ScanEye,
    Cpu,
    ArrowRight,
    Sparkles,
    CheckCircle2,
    Database,
    Eye,
    Pencil,
    Trash2,
  } from "lucide-svelte";
  import { dashboardApi, projectsApi } from "../lib/api";
  import type { DashboardStats, Project } from "../lib/types";
  import ProjectEditModal from "../lib/components/ProjectEditModal.svelte";
  import ProjectDetailsModal from "../lib/components/ProjectDetailsModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";

  export let onSelectProjectForAudit: (projectId: number) => void;
  export let onSelectProjectForViewer: (projectId: number) => void;
  export let onOpenWizard: () => void;
  export let onNavigate: (view: string) => void;

  let stats: DashboardStats = {
    total_projects: 0,
    total_documents: 0,
    total_rules: 0,
    issues_found: 34,
    db_ok: true,
    db_backend: "SUPABASE",
  };
  let recentProjects: Project[] = [];
  let isLoading = true;

  // Modals for CRUD operations on recent projects
  let isEditModalOpen = false;
  let isDetailsModalOpen = false;
  let isDeleteModalOpen = false;
  let selectedProjectForEdit: Project | null = null;
  let selectedProjectForDetails: Project | null = null;
  let projectToDelete: { id: number; name: string } | null = null;

  function openEdit(project: Project) {
    selectedProjectForEdit = project;
    isEditModalOpen = true;
  }

  function openDetails(project: Project) {
    selectedProjectForDetails = project;
    isDetailsModalOpen = true;
  }

  function promptDelete(id: number, name: string) {
    projectToDelete = { id, name };
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!projectToDelete) return;
    try {
      await projectsApi.delete(projectToDelete.id);
      recentProjects = recentProjects.filter((p) => p.id !== projectToDelete!.id);
      stats.total_projects = Math.max(0, stats.total_projects - 1);
      projectToDelete = null;
    } catch (err: any) {
      console.error("Could not delete project:", err);
    }
  }

  function handleProjectUpdated(updated: Project) {
    recentProjects = recentProjects.map((p) => (p.id === updated.id ? updated : p));
  }

  onMount(async () => {
    try {
      const [statsData, projectsData] = await Promise.all([
        dashboardApi.getStats(),
        projectsApi.list(),
      ]);
      stats = statsData;
      recentProjects = (projectsData.projects || []).slice(0, 5);
    } catch {
      // Fallback defaults
    } finally {
      isLoading = false;
    }
  });
</script>

<div class="space-y-8 mx-auto">
  <!-- Page Header -->
  <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
    <div>
      <div
        class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
      >
        Overview
      </div>
      <h1 class="text-3xl sm:text-4xl font-bold tracking-tight text-white">
        Compliance Dashboard
      </h1>
      <p class="text-sm text-slate-400 mt-1">
        High-level OpenBIM metrics and project compliance readiness.
      </p>
    </div>

    <div class="flex items-center gap-3">
      <!-- DB Status Badge -->
      <div
        class="flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium {stats.db_ok
          ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
          : 'bg-rose-950/40 text-rose-400 border-rose-800/60'}"
      >
        <span
          class="w-2 h-2 rounded-full {stats.db_ok
            ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50'
            : 'bg-rose-400'}"
        ></span>
        <span
          >DB {stats.db_backend}: {stats.db_ok ? "Connected" : "Degraded"}</span
        >
      </div>

      <!-- New Check CTA -->
      <button
        type="button"
        on:click={onOpenWizard}
        class="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
      >
        <Plus class="w-3.5 h-3.5" />
        <span>New Check</span>
      </button>
    </div>
  </div>

  {#if !stats.db_ok}
    <div
      class="p-4 rounded-2xl bg-amber-950/40 border border-amber-800 text-amber-300 text-xs flex items-center gap-2.5"
    >
      <AlertTriangle class="w-4 h-4 text-amber-400 shrink-0" />
      <span
        >Database connection is degraded. Showing fallback counters until
        persistence connectivity is restored.</span
      >
    </div>
  {/if}

  <!-- Bento Stats Grid -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- Total Projects -->
    <div
      class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all space-y-2"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span class="text-xs font-semibold uppercase tracking-wider"
          >Total Projects</span
        >
        <FolderOpen class="w-4 h-4 text-blue-400" />
      </div>
      <div class="text-3xl font-bold text-white tracking-tight">
        {stats.total_projects}
      </div>
      <div class="text-xs text-slate-400">Active in project registry</div>
    </div>

    <!-- Documents -->
    <div
      class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all space-y-2"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span class="text-xs font-semibold uppercase tracking-wider"
          >Documents</span
        >
        <BookOpen class="w-4 h-4 text-emerald-400" />
      </div>
      <div class="text-3xl font-bold text-white tracking-tight">
        {stats.total_documents}
      </div>
      <div class="text-xs text-slate-400">Uploaded specifications</div>
    </div>

    <!-- Rules Defined -->
    <div
      class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all space-y-2"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span class="text-xs font-semibold uppercase tracking-wider"
          >Rules Library</span
        >
        <ListChecks class="w-4 h-4 text-purple-400" />
      </div>
      <div class="text-3xl font-bold text-white tracking-tight">
        {stats.total_rules}
      </div>
      <div class="text-xs text-slate-400">Compliance rules active</div>
    </div>

    <!-- Issues Tracked -->
    <div
      class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all space-y-2"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span class="text-xs font-semibold uppercase tracking-wider"
          >Issues Identified</span
        >
        <AlertTriangle class="w-4 h-4 text-amber-400" />
      </div>
      <div class="text-3xl font-bold text-amber-400 tracking-tight">
        {stats.issues_found}
      </div>
      <div class="text-xs text-slate-400">Across current models</div>
    </div>
  </div>

  <!-- Recent Projects Table -->
  <div
    class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4"
  >
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold text-white tracking-tight">
          Recent Projects
        </h2>
        <p class="text-xs text-slate-400">
          Jump directly to 3D visualization or compliance analysis.
        </p>
      </div>
      <button
        type="button"
        on:click={() => onNavigate("projects")}
        class="text-xs font-semibold text-[#0071e3] hover:text-blue-400 flex items-center gap-1"
      >
        <span>View all</span>
        <ArrowRight class="w-3.5 h-3.5" />
      </button>
    </div>

    {#if recentProjects.length === 0}
      <div
        class="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl"
      >
        No projects found. Click "New Check" above to create your first project.
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead
            class="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
          >
            <tr>
              <th class="py-2.5 px-3">Name</th>
              <th class="py-2.5 px-3">Domain</th>
              <th class="py-2.5 px-3">Status</th>
              <th class="py-2.5 px-3">Model</th>
              <th class="py-2.5 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each recentProjects as project}
              <tr class="hover:bg-slate-900/60 transition-colors">
                <td class="py-3 px-3 font-semibold text-white truncate max-w-xs"
                  >{project.name}</td
                >
                <td class="py-3 px-3">
                  <span
                    class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold font-mono {project.analysis_type ===
                    'Piping'
                      ? 'bg-amber-950/60 border border-amber-800/50 text-amber-300'
                      : project.analysis_type === 'Seismic'
                      ? 'bg-purple-950/60 border border-purple-800/50 text-purple-300'
                      : 'bg-blue-950/60 border border-blue-800/50 text-blue-300'}"
                  >
                    {project.analysis_type}
                  </span>
                </td>
                <td class="py-3 px-3">
                  <span
                    class="px-2 py-0.5 rounded-full text-[10px] font-semibold {project.status ===
                    'Active'
                      ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-800/60'
                      : 'bg-slate-800 text-slate-400'}"
                  >
                    {project.status}
                  </span>
                </td>
                <td class="py-3 px-3">
                  {#if project.ifc_file_path}
                    <span
                      class="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-medium"
                    >
                      <CheckCircle2 class="w-3.5 h-3.5" />
                      <span>IFC Ready</span>
                    </span>
                  {:else}
                    <span class="text-[11px] text-slate-500">No Model</span>
                  {/if}
                </td>
                <td class="py-3 px-3 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      on:click={() => openDetails(project)}
                      class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                      title="View project details"
                    >
                      <Eye class="w-3.5 h-3.5" />
                    </button>

                    {#if project.ifc_file_path}
                      <button
                        type="button"
                        on:click={() => onSelectProjectForViewer(project.id)}
                        class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                        title="Open in 3D Viewer"
                      >
                        <ScanEye class="w-3.5 h-3.5" />
                      </button>
                    {/if}

                    <button
                      type="button"
                      on:click={() => onSelectProjectForAudit(project.id)}
                      class="px-2.5 py-1 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 hover:text-blue-300 text-xs font-semibold transition-colors"
                    >
                      Audit
                    </button>

                    <button
                      type="button"
                      on:click={() => openEdit(project)}
                      class="p-1.5 rounded-lg text-slate-400 hover:text-blue-400 hover:bg-blue-950/30 transition-colors"
                      title="Edit project"
                    >
                      <Pencil class="w-3.5 h-3.5" />
                    </button>

                    <button
                      type="button"
                      on:click={() => promptDelete(project.id, project.name)}
                      class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                      title="Delete project"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>

  <!-- Workflow Quick Guides -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
    <button
      type="button"
      on:click={() => onNavigate("extract")}
      class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-slate-700 text-left transition-all group"
    >
      <div
        class="w-9 h-9 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform"
      >
        <Sparkles class="w-4 h-4" />
      </div>
      <h3
        class="text-sm font-semibold text-white group-hover:text-purple-300 transition-colors"
      >
        Rule Extraction Studio
      </h3>
      <p class="text-xs text-slate-400 mt-1">
        Translate building code specifications into executable OpenBIM rules
        using AI.
      </p>
    </button>

    <button
      type="button"
      on:click={() => onNavigate("viewer")}
      class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-slate-700 text-left transition-all group"
    >
      <div
        class="w-9 h-9 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform"
      >
        <ScanEye class="w-4 h-4" />
      </div>
      <h3
        class="text-sm font-semibold text-white group-hover:text-cyan-300 transition-colors"
      >
        OpenBIM 3D Viewer
      </h3>
      <p class="text-xs text-slate-400 mt-1">
        Inspect spatial geometry, component properties, and BCF viewpoint
        bookmarks.
      </p>
    </button>

    <button
      type="button"
      on:click={() => onNavigate("arch")}
      class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 hover:border-slate-700 text-left transition-all group"
    >
      <div
        class="w-9 h-9 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform"
      >
        <Cpu class="w-4 h-4" />
      </div>
      <h3
        class="text-sm font-semibold text-white group-hover:text-emerald-300 transition-colors"
      >
        Architectural Audit
      </h3>
      <p class="text-xs text-slate-400 mt-1">
        Check Ontario Building Code Part 9 daylight, fire, egress and clearance
        compliance.
      </p>
    </button>
  </div>
</div>

<ProjectEditModal
  isOpen={isEditModalOpen}
  project={selectedProjectForEdit}
  onClose={() => {
    isEditModalOpen = false;
    selectedProjectForEdit = null;
  }}
  onProjectUpdated={handleProjectUpdated}
/>

<ProjectDetailsModal
  isOpen={isDetailsModalOpen}
  project={selectedProjectForDetails}
  onClose={() => {
    isDetailsModalOpen = false;
    selectedProjectForDetails = null;
  }}
  onOpenViewer={onSelectProjectForViewer}
  onOpenEnhancements={null}
/>

<ConfirmModal
  bind:isOpen={isDeleteModalOpen}
  title="Delete Project"
  message={`Are you sure you want to delete project "${projectToDelete?.name || ""}" and its associated artifacts? This cannot be undone.`}
  confirmText="Delete Project"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => (projectToDelete = null)}
/>
