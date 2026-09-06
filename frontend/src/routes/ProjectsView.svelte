<script lang="ts">
  import { onMount, onDestroy, untrack } from "svelte";
  import {
    Plus,
    Search,
    Trash2,
    Download,
    ScanEye,
    Cpu,
    Sparkles,
    CheckCircle2,
    XCircle,
    SlidersHorizontal,
    Eye,
    Pencil,
    RotateCw,
    FolderGit2,
    GitBranch,
    ExternalLink,
    Boxes,
    Box,
    Loader2,
    Database,
    ListChecks,
    BookOpen,
  } from "lucide-svelte";
  import { projectsApi, githubReposApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import type { Project, GitHubRepo, GitHubRepoStructure } from "../lib/types";
  import ProjectEditModal from "../lib/components/ProjectEditModal.svelte";
  import ProjectDetailsModal from "../lib/components/ProjectDetailsModal.svelte";
  import ProjectEnhancementsModal from "../lib/components/ProjectEnhancementsModal.svelte";
  import ProjectRulesetBindingsModal from "../lib/components/ProjectRulesetBindingsModal.svelte";
  import ProjectDocumentBindingsModal from "../lib/components/ProjectDocumentBindingsModal.svelte";
  import GitHubRepoManagerModal from "../lib/components/GitHubRepoManagerModal.svelte";
  import ProjectBulkEditModal from "../lib/components/ProjectBulkEditModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import { createTableState } from "../lib/tableState.svelte";
  import { normalizeAnalysisDomain } from "../lib/analysisDomain";
  import IsoGovernanceBadges from "../lib/components/IsoGovernanceBadges.svelte";

  interface Props {
    onSelectProjectForAudit: (projectId: number, analysisType?: string | null) => void;
    onSelectProjectForViewer: (projectId: number) => void;
    onSelectProjectForDashboard: (projectId: number) => void;
    /** The project the header's ProjectSwitcher currently has selected, if any -- the
     * target that GitHub repo models attach to. */
    selectedProject?: Project | null;
    /** Called after models are attached from a repo, to jump to that project's Models view. */
    onModelsAttached?: (projectId: number) => void;
    onOpenWizard?: () => void;
  }

  let {
    onSelectProjectForAudit,
    onSelectProjectForViewer,
    onSelectProjectForDashboard,
    selectedProject = null,
    onModelsAttached,
    onOpenWizard,
  }: Props = $props();

  // Initialize immediately from synchronous client cache for 0ms render time
  const initialCache = projectsApi.getCachedList();
  let projects: Project[] = initialCache ? initialCache.projects || [] : [];
  let isLoading = $state(!initialCache);
  let isRefreshing = $state(false);
  let error = $state("");
  let unsubscribe: (() => void) | null = null;

  // Storage Source selector state
  let selectedSource = $state("supabase"); // 'supabase' or 'repo:<id>'
  let repos: GitHubRepo[] = $state([]);
  let isRepoLoading = $state(false);
  let activeRepoStructure: GitHubRepoStructure | null = $state(null);
  let repoCategoryFilter = $state("all");
  // Repo files browsed here attach as model(s) to whichever project is
  // currently selected app-wide (the header's ProjectSwitcher) -- browsing a
  // repo never creates a new project.
  let selectedRepoPaths: Set<string> = $state(new Set());
  let primaryRepoPath: string | null = $state(null);
  let isAttaching = $state(false);

  let orgScopedProjects = $derived(
    authState.activeOrganizationId == null
      ? projects || []
      : (projects || []).filter((p) => p.organization_id === authState.activeOrganizationId),
  );

  $effect(() => {
    const _orgId = authState.activeOrganizationId;
    // loadProjects reads/writes `projects` synchronously before its first
    // await; without untrack, that read gets tracked as a dependency of this
    // effect, and the later write to `projects` (including from the
    // cache-subscribe callback) re-fires it, causing an unbounded refetch loop.
    untrack(() => loadProjects(true));
  });

  // Search, filter, sort, paginate and select — all owned by the shared state.
  // The domain filter reuses normalizeAnalysisDomain rather than restating the
  // legacy alias list ("Architectural", "Piping (Corrosive)", "Halo", ...).
  const table = $state(
    createTableState<Project, number>({
      rows: () => orgScopedProjects,
      getId: (p) => p.id,
      searchFields: (p) => [p.name, p.description],
      filters: {
        status: (p, value) => p.status === value,
        domain: (p, value) =>
          p.analysis_type === value || normalizeAnalysisDomain(p.analysis_type) === value,
      },
      initialSort: { field: "id", asc: true },
    }),
  );

  // Modals state
  let isEditModalOpen = $state(false);
  let isDetailsModalOpen = $state(false);
  let isEnhancementsOpen = $state(false);
  let isDeleteModalOpen = $state(false);
  let isRepoManagerOpen = $state(false);
  let selectedProjectForEdit: Project | null = $state(null);
  let selectedProjectForDetails: Project | null = $state(null);
  let selectedProjectForEnhance: Project | null = $state(null);
  let rulesetBindingsTarget: Project | null = $state(null);
  let documentBindingsTarget: Project | null = $state(null);

  // An owner/admin of a project's own organization is the only one who may
  // change its rule assignments -- everyone else doesn't get the button, and
  // the backend (PUT /api/projects/{id}/ruleset-bindings) enforces the same
  // rule regardless.
  let canManageRuleAssignments = $derived(
    authState.activeOrganization?.role === "owner" || authState.activeOrganization?.role === "admin",
  );
  let projectToDelete: { id: number; name: string } | null = $state(null);

  // Bulk selection state
  let isBulkEditModalOpen = $state(false);
  let isBulkDeleteModalOpen = $state(false);

  // Data loading. The view paints instantly from the synchronous client cache
  // above; these refresh it and keep it in sync with mutations made elsewhere.
  async function loadProjects(force = false) {
    if (!projects.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }
    error = "";
    try {
      const response = await projectsApi.list({ forceRefresh: force });
      projects = response.projects || [];
    } catch (err: any) {
      if (!projects.length) {
        error = err.message || "Failed to load the project registry.";
      }
    } finally {
      isLoading = false;
      isRefreshing = false;
    }
  }

  async function loadRepos() {
    try {
      repos = await githubReposApi.list();
    } catch (err: any) {
      error = err.message || "Failed to load connected GitHub repositories.";
    }
  }

  async function loadSelectedRepoStructure(repoId: number, force = false) {
    isRepoLoading = true;
    error = "";
    try {
      activeRepoStructure = await githubReposApi.getStructure(repoId, force);
    } catch (err: any) {
      activeRepoStructure = null;
      error = err.message || "Failed to read the repository structure.";
    } finally {
      isRepoLoading = false;
    }
  }

  // Switching storage source swaps which collection the table renders, so the
  // repo manifest is fetched lazily and the previous one dropped.
  async function handleSourceChange() {
    repoCategoryFilter = "all";
    selectedRepoPaths = new Set();
    primaryRepoPath = null;
    if (selectedSource.startsWith("repo:")) {
      const repoId = parseInt(selectedSource.split(":")[1], 10);
      await loadSelectedRepoStructure(repoId);
    } else {
      activeRepoStructure = null;
    }
  }

  onMount(() => {
    unsubscribe = projectsApi.subscribe((updated) => {
      projects = updated;
    });
    loadProjects();
    loadRepos();
  });

  onDestroy(() => {
    if (unsubscribe) {
      unsubscribe();
    }
  });

  let filteredRepoItems = $derived(
    (activeRepoStructure?.items || []).filter((item) => {
      const matchesSearch =
        table.search === "" ||
        item.name.toLowerCase().includes(table.search.toLowerCase()) ||
        item.path.toLowerCase().includes(table.search.toLowerCase());
      const matchesCategory = repoCategoryFilter === "all" || item.category === repoCategoryFilter;
      return matchesSearch && matchesCategory;
    }),
  );

  function toggleRepoPath(path: string) {
    const next = new Set(selectedRepoPaths);
    if (next.has(path)) {
      next.delete(path);
      if (primaryRepoPath === path) primaryRepoPath = next.values().next().value ?? null;
    } else {
      next.add(path);
      if (!primaryRepoPath) primaryRepoPath = path;
    }
    selectedRepoPaths = next;
  }

  function toggleAllRepoPaths() {
    if (selectedRepoPaths.size === filteredRepoItems.length && filteredRepoItems.length > 0) {
      selectedRepoPaths = new Set();
      primaryRepoPath = null;
    } else {
      selectedRepoPaths = new Set(filteredRepoItems.map((item) => item.path));
      primaryRepoPath = filteredRepoItems[0]?.path ?? null;
    }
  }

  async function handleAttachSelectedModels() {
    if (!selectedProject || !selectedSource.startsWith("repo:") || selectedRepoPaths.size === 0) {
      return;
    }
    const repoId = parseInt(selectedSource.split(":")[1], 10);
    const filePaths = Array.from(selectedRepoPaths);
    const primaryIndex = Math.max(0, filePaths.indexOf(primaryRepoPath || filePaths[0]));

    isAttaching = true;
    error = "";
    try {
      await githubReposApi.attachModelsToProject(selectedProject.id, {
        repo_id: repoId,
        file_paths: filePaths,
        primary_index: primaryIndex,
      });
      toasts.success(
        `Attached ${filePaths.length} model${filePaths.length === 1 ? "" : "s"} to "${selectedProject.name}".`,
      );
      selectedRepoPaths = new Set();
      primaryRepoPath = null;
      onModelsAttached?.(selectedProject.id);
    } catch (err: any) {
      error = err.message || "Failed to attach model(s) from GitHub repository.";
    } finally {
      isAttaching = false;
    }
  }

  function promptDelete(projectId: number, name: string) {
    projectToDelete = { id: projectId, name };
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!projectToDelete) return;
    try {
      await projectsApi.delete(projectToDelete.id);
      projects = projects.filter((p) => p.id !== projectToDelete!.id);
      table.selectedIds.delete(projectToDelete!.id);
      projectToDelete = null;
    } catch (err: any) {
      error = `Could not delete project: ${err.message}`;
    }
  }

  async function confirmBulkDelete() {
    if (!table.selectedCount) return;
    try {
      await projectsApi.bulkDelete(table.selectedIdList);
      projects = projects.filter((p) => !table.selectedIds.has(p.id));
      table.clearSelection();
      isBulkDeleteModalOpen = false;
    } catch (err: any) {
      error = `Could not delete selected projects: ${err.message}`;
    }
  }

  async function handleBulkUpdated() {
    await loadProjects(true);
    table.clearSelection();
  }

  function openEnhancements(project: Project) {
    selectedProjectForEnhance = project;
    isEnhancementsOpen = true;
  }

  function openEdit(project: Project) {
    selectedProjectForEdit = project;
    isEditModalOpen = true;
  }

  function openDetails(project: Project) {
    selectedProjectForDetails = project;
    isDetailsModalOpen = true;
  }

  function handleProjectUpdated(updated: Project) {
    projects = projects.map((p) => (p.id === updated.id ? updated : p));
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header & Storage Source Control -->
  <!-- Header & Storage Source Control -->
  <PageHeader
    category="Registry"
    title="Project Registry"
    subtitle="Manage OpenBIM models, analysis scopes, and project storage sources."
    icon={Box}
  >
    {#snippet actions()}
      <div class="flex flex-wrap items-center gap-2.5">
        {#if onOpenWizard}
          <button
            type="button"
            onclick={onOpenWizard}
            class="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
          >
            <Plus class="h-3.5 w-3.5" />
            <span>New Project</span>
          </button>
        {/if}
      <div
        class="flex flex-wrap items-center gap-2.5 rounded-2xl border border-slate-800 bg-slate-900/90 p-2"
      >
        <div class="flex items-center gap-2 px-2">
          {#if selectedSource === "supabase"}
            <Database class="h-4 w-4 text-emerald-400" />
          {:else}
            <FolderGit2 class="h-4 w-4 text-blue-400" />
          {/if}
          <span class="whitespace-nowrap text-xs font-semibold text-slate-300">Storage Source:</span
          >
        </div>

        <select
          bind:value={selectedSource}
          onchange={handleSourceChange}
          class="max-w-[240px] truncate rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs font-semibold text-slate-50 focus:border-blue-500 focus:outline-none"
        >
          <option value="supabase">Supabase Database (Main Registry)</option>
          {#if repos.length > 0}
            <optgroup label="GitHub Repositories">
              {#each repos as repo (repo.id)}
                <option value={`repo:${repo.id}`}>
                  {repo.owner}/{repo.name} ({repo.branch})
                </option>
              {/each}
            </optgroup>
          {/if}
        </select>

        <button
          type="button"
          onclick={() => (isRepoManagerOpen = true)}
          class="flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-800"
          title="Manage GitHub Repositories (Add, Edit, Delete)"
        >
          <Plus class="h-3.5 w-3.5 text-blue-400" />
          <span>Manage Repos</span>
        </button>

        {#if selectedSource === "supabase"}
          <button
            type="button"
            onclick={() => loadProjects(true)}
            class="rounded-xl border border-slate-800 bg-slate-950 p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
            title="Refresh project registry"
          >
            <RotateCw class="h-3.5 w-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
          </button>
        {:else if selectedSource.startsWith("repo:")}
          <button
            type="button"
            onclick={() => {
              const repoId = parseInt(selectedSource.split(":")[1], 10);
              loadSelectedRepoStructure(repoId, true);
            }}
            class="flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-800"
            title="Re-sync GitHub repository models & manifest"
          >
            <RotateCw class="h-3.5 w-3.5 {isRepoLoading ? 'animate-spin text-blue-400' : ''}" />
            <span>Sync Repo</span>
          </button>
        {/if}
      </div>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
      {error}
    </div>
  {/if}

  <!-- VIEW 1: SUPABASE INTERNAL DATABASE PROJECTS (MAIN REGISTRY) -->
  {#if selectedSource === "supabase"}
    <!-- Filters and Search Bar -->
    <div
      class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 md:flex-row"
    >
      <div class="relative w-full flex-1">
        <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          bind:value={table.search}
          placeholder="Filter projects by name or description..."
          class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
        />
      </div>

      <div class="flex w-full items-center gap-2 md:w-auto">
        <select
          bind:value={table.filters.status}
          class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          <option value="all">All Statuses</option>
          <option value="Active">Active</option>
          <option value="Draft">Draft</option>
          <option value="Archived">Archived</option>
        </select>

        <select
          bind:value={table.filters.domain}
          class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          <option value="all">All Domains</option>
          <option value="Arch">Arch</option>
          <option value="Piping">Piping</option>
          <option value="seismic">seismic</option>
        </select>
      </div>
    </div>

    <!-- Bulk Operations Toolbar -->
    <BulkActionBar
      selectedCount={table.selectedCount}
      itemLabel="project"
      onClearSelection={() => table.clearSelection()}
      onBulkEdit={() => (isBulkEditModalOpen = true)}
      onBulkDelete={() => (isBulkDeleteModalOpen = true)}
    />

    <!-- Projects Table -->
    <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
      {#if isLoading}
        <LoadingState message="Loading project registry..." />
      {:else if table.totalItems === 0}
        <div class="p-6">
          <EmptyState
            title="No projects match your current filters"
            description="Adjust your search criteria or create a project using the Wizard."
            actionLabel="Reset filters"
            onAction={() => {
              table.reset();
            }}
          />
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead
              class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
            >
              <tr>
                <th class="w-10 px-4 py-3">
                  <TableCheckbox
                    checked={table.allFilteredSelected}
                    indeterminate={table.someFilteredSelected}
                    onchange={() => table.toggleSelectAll()}
                    title="Select or deselect all visible projects"
                  />
                </th>
                <SortHeader
                  column="name"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                >
                  Project Name
                </SortHeader>
                <SortHeader
                  column="status"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                >
                  Status
                </SortHeader>
                <th class="px-4 py-3">IFC Model</th>
                <SortHeader
                  column="analysis_type"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                >
                  Analysis Domain
                </SortHeader>
                <SortHeader
                  column="jurisdiction"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                >
                  Jurisdiction
                </SortHeader>
                <SortHeader
                  column="created_at"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                >
                  Created
                </SortHeader>
                <th class="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#each table.paginated as project (project.id)}
                <tr
                  class="transition-colors hover:bg-slate-900/60 {table.isSelected(project.id)
                    ? 'bg-blue-950/20'
                    : ''}"
                >
                  <td class="w-10 px-4 py-3">
                    <TableCheckbox
                      checked={table.isSelected(project.id)}
                      onchange={() => table.toggleSelect(project.id)}
                      ariaLabel={`Select project ${project.name}`}
                    />
                  </td>
                  <td class="px-4 py-3 font-semibold text-slate-50">
                    <div class="flex flex-col items-start">
                      <button
                        type="button"
                        onclick={() => onSelectProjectForDashboard(project.id)}
                        class="text-left text-sm text-slate-50 transition-colors hover:text-accent hover:underline"
                        title="Open project"
                      >
                        {project.name}
                      </button>
                      {#if project.description}
                        <span class="max-w-sm truncate text-caption font-normal text-slate-400">
                          {project.description}
                        </span>
                      {/if}
                    </div>
                  </td>
                  <td class="px-4 py-3">
                    <span
                      class="inline-block rounded-md border px-2.5 py-0.5 text-micro font-semibold {project.status ===
                      'Active'
                        ? 'border-emerald-800/60 bg-emerald-950/40 text-emerald-400'
                        : project.status === 'Archived'
                          ? 'border-slate-700 bg-slate-800 text-slate-400'
                          : 'border-amber-800/60 bg-amber-950/40 text-amber-400'}"
                    >
                      {project.status}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    {#if project.ifc_file_path}
                      <div class="flex items-center gap-1.5 font-medium text-emerald-400">
                        <CheckCircle2 class="h-4 w-4 text-emerald-400" />
                        <span
                          class="max-w-[120px] truncate text-caption"
                          title={project.ifc_file_path}>Attached</span
                        >
                      </div>
                    {:else}
                      <div class="flex items-center gap-1.5 text-slate-500">
                        <XCircle class="h-4 w-4" />
                        <span class="text-caption">None</span>
                      </div>
                    {/if}
                  </td>
                  <td class="px-4 py-3">
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
                  <td class="px-4 py-3 text-slate-400">{project.country}</td>
                  <td class="whitespace-nowrap px-4 py-3 text-slate-500">
                    {project.created_at ? project.created_at.substring(0, 10) : "-"}
                  </td>
                  <td class="whitespace-nowrap px-4 py-3 text-right">
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

                        <button
                          type="button"
                          onclick={() => openEnhancements(project)}
                          class="rounded-lg border border-purple-800/40 bg-purple-950/40 p-1.5 text-purple-300 transition-colors hover:bg-purple-900/60"
                          title="Model Quality Improvements (Lineage)"
                        >
                          <Sparkles class="h-3.5 w-3.5" />
                        </button>
                      {/if}

                      <button
                        type="button"
                        onclick={() => onSelectProjectForAudit(project.id, project.analysis_type)}
                        class="rounded-lg bg-blue-600/20 px-2.5 py-1 text-xs font-semibold text-blue-400 transition-colors hover:bg-blue-600/30 hover:text-blue-300"
                      >
                        Audit
                      </button>

                      {#if canManageRuleAssignments}
                        <button
                          type="button"
                          onclick={() => (rulesetBindingsTarget = project)}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-emerald-950/30 hover:text-emerald-400"
                          title="Rule Assignments"
                        >
                          <ListChecks class="h-3.5 w-3.5" />
                        </button>

                        <button
                          type="button"
                          onclick={() => (documentBindingsTarget = project)}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-emerald-950/30 hover:text-emerald-400"
                          title="Document Assignments"
                        >
                          <BookOpen class="h-3.5 w-3.5" />
                        </button>
                      {/if}

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

        <TablePagination
          currentPage={table.page}
          pageSize={table.pageSize}
          totalItems={table.totalItems}
          onPageChange={(p) => (table.requestedPage = p)}
          onPageSizeChange={(size) => {
            table.pageSize = size;
            table.requestedPage = 1;
          }}
        />
      {/if}
    </div>
  {/if}

  <!-- VIEW 2: GITHUB REPOSITORY STORAGE DISCOVERY -->
  {#if selectedSource.startsWith("repo:")}
    <div class="space-y-4">
      {#if isRepoLoading}
        <div
          class="flex items-center justify-center gap-2 rounded-2xl border border-slate-800 bg-slate-900/40 p-12 text-center text-xs text-slate-400"
        >
          <Loader2 class="h-4 w-4 animate-spin text-blue-400" />
          <span>Reading GitHub repository structure & OpenBIM models tree...</span>
        </div>
      {:else if activeRepoStructure}
        <!-- Repo Banner -->
        <div
          class="flex flex-col items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 md:flex-row md:items-center"
        >
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <FolderGit2 class="h-5 w-5 text-blue-400" />
              <h2 class="text-lg font-bold text-slate-50">
                {activeRepoStructure.owner}/{activeRepoStructure.name}
              </h2>
              <span
                class="inline-flex items-center gap-1 rounded border border-slate-800 bg-slate-950 px-2 py-0.5 font-mono text-caption text-slate-400"
              >
                <GitBranch class="h-3 w-3 text-blue-400" />
                {activeRepoStructure.branch}
              </span>
            </div>
            <p class="text-xs text-slate-400">
              Discovered <span class="font-semibold text-blue-400"
                >{activeRepoStructure.models_count}</span
              >
              OpenBIM models across
              <span class="font-semibold text-slate-300"
                >{activeRepoStructure.categories.length}</span
              > category folders.
            </p>
          </div>

          <div class="flex items-center gap-2">
            <a
              href={activeRepoStructure.url}
              target="_blank"
              rel="noopener noreferrer"
              class="flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs font-semibold text-blue-400 transition-colors hover:bg-slate-800"
            >
              <span>GitHub Repo</span>
              <ExternalLink class="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        <!-- Target project: repo files attach as model(s) to whichever project is
             currently selected app-wide, they never create a new one. -->
        {#if selectedProject}
          <div
            class="flex items-center gap-2.5 rounded-2xl border border-blue-800/40 bg-blue-950/20 p-3.5 text-xs"
          >
            <Boxes class="h-4 w-4 shrink-0 text-blue-400" />
            <span class="text-slate-300"
              >Selected models will attach to <span class="font-semibold text-slate-50"
                >{selectedProject.name}</span
              > — switch projects from the header to attach elsewhere.</span
            >
          </div>
        {:else}
          <div
            class="flex items-center gap-2.5 rounded-2xl border border-amber-800/40 bg-amber-950/20 p-3.5 text-xs text-amber-300"
          >
            <XCircle class="h-4 w-4 shrink-0" />
            <span>Select a project from the header switcher before attaching a model.</span>
          </div>
        {/if}

        <!-- Filter Bar -->
        <div
          class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 md:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              bind:value={table.search}
              placeholder="Search repository IFC models by filename or path..."
              class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            />
          </div>

          {#if activeRepoStructure.categories.length > 0}
            <div class="flex w-full items-center gap-2 md:w-auto">
              <select
                bind:value={repoCategoryFilter}
                class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-blue-500 focus:outline-none"
              >
                <option value="all">All Category Folders</option>
                {#each activeRepoStructure.categories as cat (cat)}
                  <option value={cat}>{cat}</option>
                {/each}
              </select>
            </div>
          {/if}
        </div>

        <!-- Repo Models Table -->
        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
          {#if filteredRepoItems.length === 0}
            <div class="p-12 text-center text-xs text-slate-500">
              No OpenBIM models found matching your search or category filter.
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs text-slate-300">
                <thead
                  class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
                >
                  <tr>
                    <th class="w-10 px-4 py-3">
                      <TableCheckbox
                        checked={selectedRepoPaths.size > 0 &&
                          selectedRepoPaths.size === filteredRepoItems.length}
                        indeterminate={selectedRepoPaths.size > 0 &&
                          selectedRepoPaths.size < filteredRepoItems.length}
                        onchange={toggleAllRepoPaths}
                        title="Select or deselect all visible models"
                      />
                    </th>
                    <th class="px-4 py-3">IFC Model Name</th>
                    <th class="px-4 py-3">Repository Path</th>
                    <th class="px-4 py-3">Category</th>
                    <th class="px-4 py-3">Size</th>
                    <th class="px-4 py-3 text-center">Primary</th>
                    <th class="px-4 py-3 text-right">Download</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60">
                  {#each filteredRepoItems as item (item.path)}
                    {@const isSelected = selectedRepoPaths.has(item.path)}
                    <tr
                      class="transition-colors hover:bg-slate-900/60 {isSelected
                        ? 'bg-blue-950/20'
                        : ''}"
                    >
                      <td class="w-10 px-4 py-3">
                        <TableCheckbox
                          checked={isSelected}
                          onchange={() => toggleRepoPath(item.path)}
                          ariaLabel={`Select ${item.name}`}
                        />
                      </td>
                      <td class="px-4 py-3 font-semibold text-slate-50">
                        <div class="flex items-center gap-2">
                          <Box class="h-4 w-4 shrink-0 text-blue-400" />
                          <span class="text-sm">{item.name}</span>
                        </div>
                      </td>
                      <td
                        class="max-w-xs truncate px-4 py-3 font-mono text-caption text-slate-400"
                        title={item.path}
                      >
                        {item.path}
                      </td>
                      <td class="px-4 py-3">
                        <span
                          class="inline-block rounded border border-slate-700 bg-slate-800 px-2 py-0.5 font-mono text-micro font-semibold uppercase text-slate-300"
                        >
                          {item.category}
                        </span>
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 text-slate-400">
                        {formatBytes(item.size)}
                      </td>
                      <td class="px-4 py-3 text-center">
                        {#if isSelected}
                          <input
                            type="radio"
                            name="primary-repo-model"
                            checked={primaryRepoPath === item.path}
                            onchange={() => (primaryRepoPath = item.path)}
                            title="Set as this project's primary model"
                          />
                        {/if}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 text-right">
                        <a
                          href={item.download_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          class="inline-flex rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                          title="Direct download raw IFC"
                        >
                          <Download class="h-3.5 w-3.5" />
                        </a>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Attach action bar: mirrors BulkActionBar's floating pattern, shown
         once at least one repo model is checked. -->
    {#if selectedRepoPaths.size > 0}
      <div
        class="sticky bottom-4 z-10 flex items-center justify-between gap-4 rounded-2xl border border-blue-800/60 bg-slate-900 p-4 shadow-lg shadow-black/40"
      >
        <span class="text-xs font-medium text-slate-300">
          {selectedRepoPaths.size} model{selectedRepoPaths.size === 1 ? "" : "s"} selected
        </span>
        <button
          type="button"
          onclick={handleAttachSelectedModels}
          disabled={!selectedProject || isAttaching}
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {#if isAttaching}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
            <span>Attaching…</span>
          {:else}
            <Boxes class="h-3.5 w-3.5" />
            <span
              >Attach to {selectedProject
                ? selectedProject.name
                : "a project"}</span
            >
          {/if}
        </button>
      </div>
    {/if}
  {/if}
</div>

<!-- Modals -->
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
  onOpenEnhancements={openEnhancements}
/>

<ProjectEnhancementsModal
  isOpen={isEnhancementsOpen}
  project={selectedProjectForEnhance}
  onClose={() => {
    isEnhancementsOpen = false;
    selectedProjectForEnhance = null;
  }}
/>

<ProjectRulesetBindingsModal
  project={rulesetBindingsTarget}
  onClose={() => (rulesetBindingsTarget = null)}
/>

<ProjectDocumentBindingsModal
  project={documentBindingsTarget}
  onClose={() => (documentBindingsTarget = null)}
/>

<GitHubRepoManagerModal
  isOpen={isRepoManagerOpen}
  onClose={() => (isRepoManagerOpen = false)}
  onReposUpdated={() => {
    loadRepos();
    if (selectedSource.startsWith("repo:")) {
      handleSourceChange();
    }
  }}
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

<ProjectBulkEditModal
  isOpen={isBulkEditModalOpen}
  selectedProjectIds={table.selectedIdList}
  onClose={() => (isBulkEditModalOpen = false)}
  onBulkUpdated={handleBulkUpdated}
/>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title="Delete Selected Projects"
  message={`Are you sure you want to delete ${table.selectedCount} project(s) and their associated artifacts? This cannot be undone.`}
  confirmText={`Delete ${table.selectedCount} Project(s)`}
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => (isBulkDeleteModalOpen = false)}
/>
