<script lang="ts">
  import { onMount, onDestroy } from "svelte";
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
    RotateCw,
  } from "lucide-svelte";
  import { dashboardApi, projectsApi } from "../lib/api";
  import type { DashboardStats, Project } from "../lib/types";
  import ProjectEditModal from "../lib/components/ProjectEditModal.svelte";
  import ProjectDetailsModal from "../lib/components/ProjectDetailsModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";

  interface Props {
    onSelectProjectForAudit: (projectId: number) => void;
    onSelectProjectForViewer: (projectId: number) => void;
    onOpenWizard: () => void;
    onNavigate: (view: string) => void;
  }

  let { onSelectProjectForAudit, onSelectProjectForViewer, onOpenWizard, onNavigate }: Props =
    $props();

  const cachedStats = dashboardApi.getCachedStats();
  const cachedProjects = projectsApi.getCachedList();

  let stats: DashboardStats = $state(
    cachedStats || {
      total_projects: cachedProjects ? cachedProjects.total : 0,
      total_documents: 0,
      total_rules: 0,
      issues_found: 0,
      db_ok: true,
      db_backend: "SUPABASE",
    },
  );
  let recentProjects: Project[] = $state(
    cachedProjects ? (cachedProjects.projects || []).slice(0, 5) : [],
  );
  let isLoading = !cachedStats && !cachedProjects;
  let isRefreshing = false;
  let unsubscribeProjects: (() => void) | null = null;

  // Modals for CRUD operations on recent projects
  let isEditModalOpen = $state(false);
  let isDetailsModalOpen = $state(false);
  let isDeleteModalOpen = $state(false);
  let selectedProjectForEdit: Project | null = $state(null);
  let selectedProjectForDetails: Project | null = $state(null);
  let projectToDelete: { id: number; name: string } | null = $state(null);

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

  async function refreshDashboard(force = false) {
    if (!cachedStats && !recentProjects.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }

    try {
      const [statsData, projectsData] = await Promise.all([
        dashboardApi.getStats({ forceRefresh: force }),
        projectsApi.list({ forceRefresh: force }),
      ]);
      stats = statsData;
      recentProjects = (projectsData.projects || []).slice(0, 5);
    } catch {
      // Keep cached or fallback
    } finally {
      isLoading = false;
      isRefreshing = false;
    }
  }

  onMount(() => {
    unsubscribeProjects = projectsApi.subscribe((updatedProjects) => {
      recentProjects = updatedProjects.slice(0, 5);
      stats = { ...stats, total_projects: updatedProjects.length };
    });

    // Load fresh data
    refreshDashboard();

    // Proactively warm up and prefetch all other pages from the dashboard
    dashboardApi.prefetchAll();
  });

  onDestroy(() => {
    if (unsubscribeProjects) {
      unsubscribeProjects();
    }
  });
</script>

<div class="mx-auto space-y-8">
  <!-- Page Header -->
  <PageHeader
    category="Overview"
    title="Compliance Dashboard"
    subtitle="High-level OpenBIM metrics and project compliance readiness."
  >
    {#snippet actions()}
      <div class="flex items-center gap-3">
        <!-- New Project CTA -->
        <button
          type="button"
          onclick={onOpenWizard}
          class="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
        >
          <Plus class="h-3.5 w-3.5" />
          <span>New Project</span>
        </button>
      </div>
    {/snippet}
  </PageHeader>

  {#if !stats.db_ok}
    <div
      class="flex items-center gap-2.5 rounded-2xl border border-amber-800 bg-amber-950/40 p-4 text-xs text-amber-300"
    >
      <AlertTriangle class="h-4 w-4 shrink-0 text-amber-400" />
      <span
        >Database connection is degraded. Showing fallback counters until persistence connectivity
        is restored.</span
      >
    </div>
  {/if}

  <!-- Bento Stats Grid -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
    <!-- Total Projects -->
    <button
      type="button"
      onclick={() => onNavigate("projects")}
      class="group w-full cursor-pointer space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-left transition-all hover:scale-[1.01] hover:border-slate-700 hover:bg-slate-900/80 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span
          class="text-xs font-semibold uppercase tracking-wider transition-colors group-hover:text-slate-300"
          >Total Projects</span
        >
        <FolderOpen class="h-4 w-4 text-blue-400 transition-transform group-hover:scale-110" />
      </div>
      <div class="text-3xl font-bold tracking-tight text-slate-50">
        {stats.total_projects}
      </div>
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span>Active in project registry</span>
        <ArrowRight
          class="h-3.5 w-3.5 -translate-x-1 text-blue-400 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100"
        />
      </div>
    </button>

    <!-- Documents -->
    <button
      type="button"
      onclick={() => onNavigate("documents")}
      class="group w-full cursor-pointer space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-left transition-all hover:scale-[1.01] hover:border-slate-700 hover:bg-slate-900/80 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span
          class="text-xs font-semibold uppercase tracking-wider transition-colors group-hover:text-slate-300"
          >Documents</span
        >
        <BookOpen class="h-4 w-4 text-emerald-400 transition-transform group-hover:scale-110" />
      </div>
      <div class="text-3xl font-bold tracking-tight text-slate-50">
        {stats.total_documents}
      </div>
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span>Uploaded specifications</span>
        <ArrowRight
          class="h-3.5 w-3.5 -translate-x-1 text-emerald-400 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100"
        />
      </div>
    </button>

    <!-- Rules Defined -->
    <button
      type="button"
      onclick={() => onNavigate("rules")}
      class="group w-full cursor-pointer space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-left transition-all hover:scale-[1.01] hover:border-slate-700 hover:bg-slate-900/80 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span
          class="text-xs font-semibold uppercase tracking-wider transition-colors group-hover:text-slate-300"
          >Rules Library</span
        >
        <ListChecks class="h-4 w-4 text-purple-400 transition-transform group-hover:scale-110" />
      </div>
      <div class="text-3xl font-bold tracking-tight text-slate-50">
        {stats.total_rules}
      </div>
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span>Compliance rules active</span>
        <ArrowRight
          class="h-3.5 w-3.5 -translate-x-1 text-purple-400 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100"
        />
      </div>
    </button>

    <!-- Issues Tracked -->
    <button
      type="button"
      onclick={() => onNavigate("reports")}
      class="group w-full cursor-pointer space-y-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 text-left transition-all hover:scale-[1.01] hover:border-slate-700 hover:bg-slate-900/80 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
    >
      <div class="flex items-center justify-between text-slate-400">
        <span
          class="text-xs font-semibold uppercase tracking-wider transition-colors group-hover:text-slate-300"
          >Issues Identified</span
        >
        <AlertTriangle class="h-4 w-4 text-amber-400 transition-transform group-hover:scale-110" />
      </div>
      <div class="text-3xl font-bold tracking-tight text-amber-400">
        {stats.issues_found}
      </div>
      <div class="flex items-center justify-between text-xs text-slate-400">
        <span>Across current models</span>
        <ArrowRight
          class="h-3.5 w-3.5 -translate-x-1 text-amber-400 opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100"
        />
      </div>
    </button>
  </div>

  <!-- Recent Projects Table -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold tracking-tight text-slate-50">Recent Projects</h2>
        <p class="text-xs text-slate-400">
          Jump directly to 3D visualization or compliance analysis.
        </p>
      </div>
      <button
        type="button"
        onclick={() => onNavigate("projects")}
        class="flex items-center gap-1 text-xs font-semibold text-accent hover:text-blue-400"
      >
        <span>View all</span>
        <ArrowRight class="h-3.5 w-3.5" />
      </button>
    </div>

    {#if recentProjects.length === 0}
      <div
        class="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500"
      >
        No projects found. Click "New Project" to create your first project.
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead
            class="border-b border-slate-800 text-caption font-semibold uppercase tracking-wider text-slate-400"
          >
            <tr>
              <th class="px-3 py-2.5">Name</th>
              <th class="px-3 py-2.5">Domain</th>
              <th class="px-3 py-2.5">Status</th>
              <th class="px-3 py-2.5">Model</th>
              <th class="px-3 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each recentProjects as project (project.id)}
              <tr class="transition-colors hover:bg-slate-900/60">
                <td class="max-w-xs truncate px-3 py-3 font-semibold text-slate-50"
                  >{project.name}</td
                >
                <td class="px-3 py-3">
                  <span
                    class="inline-block rounded px-2 py-0.5 font-mono text-micro font-semibold {project.analysis_type ===
                    'Piping'
                      ? 'border border-amber-800/50 bg-amber-950/60 text-amber-300'
                      : project.analysis_type === 'Seismic'
                        ? 'border border-purple-800/50 bg-purple-950/60 text-purple-300'
                        : 'border border-blue-800/50 bg-blue-950/60 text-blue-300'}"
                  >
                    {project.analysis_type}
                  </span>
                </td>
                <td class="px-3 py-3">
                  <span
                    class="rounded-full px-2 py-0.5 text-micro font-semibold {project.status ===
                    'Active'
                      ? 'border border-emerald-800/60 bg-emerald-950/50 text-emerald-400'
                      : 'bg-slate-800 text-slate-400'}"
                  >
                    {project.status}
                  </span>
                </td>
                <td class="px-3 py-3">
                  {#if project.ifc_file_path}
                    <span
                      class="inline-flex items-center gap-1 text-caption font-medium text-emerald-400"
                    >
                      <CheckCircle2 class="h-3.5 w-3.5" />
                      <span>IFC Ready</span>
                    </span>
                  {:else}
                    <span class="text-caption text-slate-500">No Model</span>
                  {/if}
                </td>
                <td class="px-3 py-3 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      onclick={() => openDetails(project)}
                      class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                      title="View project details"
                    >
                      <Eye class="h-3.5 w-3.5" />
                    </button>

                    {#if project.ifc_file_path}
                      <button
                        type="button"
                        onclick={() => onSelectProjectForViewer(project.id)}
                        class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                        title="Open in 3D Viewer"
                      >
                        <ScanEye class="h-3.5 w-3.5" />
                      </button>
                    {/if}

                    <button
                      type="button"
                      onclick={() => onSelectProjectForAudit(project.id)}
                      class="rounded-lg bg-blue-600/20 px-2.5 py-1 text-xs font-semibold text-blue-400 transition-colors hover:bg-blue-600/30 hover:text-blue-300"
                    >
                      Audit
                    </button>

                    <button
                      type="button"
                      onclick={() => openEdit(project)}
                      class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-blue-950/30 hover:text-blue-400"
                      title="Edit project"
                    >
                      <Pencil class="h-3.5 w-3.5" />
                    </button>

                    <button
                      type="button"
                      onclick={() => promptDelete(project.id, project.name)}
                      class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                      title="Delete project"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
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
  <div class="grid grid-cols-1 gap-4 pt-2 md:grid-cols-3">
    <button
      type="button"
      onclick={() => onNavigate("extract")}
      class="group rounded-2xl border border-slate-800 bg-slate-900/40 p-5 text-left transition-all hover:border-slate-700"
    >
      <div
        class="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 transition-transform group-hover:scale-110"
      >
        <Sparkles class="h-4 w-4" />
      </div>
      <h3 class="text-sm font-semibold text-slate-50 transition-colors group-hover:text-purple-300">
        Rule Extraction Studio
      </h3>
      <p class="mt-1 text-xs text-slate-400">
        Translate building code specifications into executable OpenBIM rules using AI.
      </p>
    </button>

    <button
      type="button"
      onclick={() => onNavigate("viewer")}
      class="group rounded-2xl border border-slate-800 bg-slate-900/40 p-5 text-left transition-all hover:border-slate-700"
    >
      <div
        class="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-400 transition-transform group-hover:scale-110"
      >
        <ScanEye class="h-4 w-4" />
      </div>
      <h3 class="text-sm font-semibold text-slate-50 transition-colors group-hover:text-cyan-300">
        OpenBIM 3D Viewer
      </h3>
      <p class="mt-1 text-xs text-slate-400">
        Inspect spatial geometry, component properties, and BCF viewpoint bookmarks.
      </p>
    </button>

    <button
      type="button"
      onclick={() => onNavigate("arch")}
      class="group rounded-2xl border border-slate-800 bg-slate-900/40 p-5 text-left transition-all hover:border-slate-700"
    >
      <div
        class="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 transition-transform group-hover:scale-110"
      >
        <Cpu class="h-4 w-4" />
      </div>
      <h3
        class="text-sm font-semibold text-slate-50 transition-colors group-hover:text-emerald-300"
      >
        Architectural Audit
      </h3>
      <p class="mt-1 text-xs text-slate-400">
        Check Ontario Building Code Part 9 daylight, fire, egress and clearance compliance.
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
