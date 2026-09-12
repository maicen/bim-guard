<script lang="ts">
  import { onMount, onDestroy, untrack } from "svelte";
  import {
    BookOpen,
    ListChecks,
    AlertTriangle,
    ScanEye,
    Sparkles,
    CheckCircle2,
    XCircle,
    Eye,
    Pencil,
    Trash2,
    Search,
    Building2,
  } from "lucide-svelte";
  import { dashboardApi, projectsApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import type { DashboardStats, Project } from "../lib/types";
  import ProjectEditModal from "../lib/components/ProjectEditModal.svelte";
  import ProjectDetailsModal from "../lib/components/ProjectDetailsModal.svelte";
  import ProjectEnhancementsModal from "../lib/components/ProjectEnhancementsModal.svelte";
  import ProjectRulesetBindingsModal from "../lib/components/ProjectRulesetBindingsModal.svelte";
  import ProjectDocumentBindingsModal from "../lib/components/ProjectDocumentBindingsModal.svelte";
  import ProjectBulkEditModal from "../lib/components/ProjectBulkEditModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import { createTableState } from "../lib/tableState.svelte";
  import {
    normalizeAnalysisDomain,
    formatAnalysisDomain,
    getDomainBadgeClasses,
  } from "../lib/analysisDomain";

  interface Props {
    onSelectProjectForAudit: (projectId: number, analysisType?: string | null) => void;
    onSelectProjectForViewer: (projectId: number) => void;
    onSelectProjectForDashboard: (projectId: number) => void;
  }

  let {
    onSelectProjectForAudit,
    onSelectProjectForViewer,
    onSelectProjectForDashboard,
  }: Props = $props();

  const cachedStats = dashboardApi.getCachedStats();
  const cachedProjects = projectsApi.getCachedList();

  // Only db_ok/db_backend (the "degraded connectivity" banner below) come
  // from the stats endpoint now -- the project count tiles it used to also
  // carry were removed from this view; the project list itself still comes
  // from projectsApi, independent of this.
  let stats: DashboardStats = $state(
    cachedStats || {
      db_ok: true,
      db_backend: "SUPABASE",
    },
  );
  let projects: Project[] = $state(cachedProjects ? cachedProjects.projects || [] : []);
  let isLoading = $state(!cachedStats && !cachedProjects);
  let isRefreshing = $state(false);
  let error = $state("");
  let unsubscribeProjects: (() => void) | null = null;

  // Search, filter, sort, paginate and select for the project registry table.
  // `projects` is already org-scoped server-side (including projects shared
  // into this org, whose own organization_id points to the owning org) --
  // re-filtering here by strict organization_id equality would drop those
  // shared-in projects even though the API correctly returned them.
  const table = $state(
    createTableState<Project, number>({
      rows: () => projects || [],
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

  // Modals for CRUD operations on projects
  let isEditModalOpen = $state(false);
  let isDetailsModalOpen = $state(false);
  let isEnhancementsOpen = $state(false);
  let isDeleteModalOpen = $state(false);
  let selectedProjectForEdit: Project | null = $state(null);
  let selectedProjectForDetails: Project | null = $state(null);
  let selectedProjectForEnhance: Project | null = $state(null);
  let rulesetBindingsTarget: Project | null = $state(null);
  let documentBindingsTarget: Project | null = $state(null);
  let projectToDelete: { id: number; name: string } | null = $state(null);

  // Bulk selection state
  let isBulkEditModalOpen = $state(false);
  let isBulkDeleteModalOpen = $state(false);

  // An owner/admin of a project's own organization is the only one who may
  // change its rule assignments -- everyone else doesn't get the button, and
  // the backend (PUT /api/projects/{id}/ruleset-bindings) enforces the same
  // rule regardless.
  let canManageRuleAssignments = $derived(
    authState.activeOrganization?.role === "owner" || authState.activeOrganization?.role === "admin",
  );

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

  function promptDelete(id: number, name: string) {
    projectToDelete = { id, name };
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
    await refreshDashboard(true);
    table.clearSelection();
  }

  function handleProjectUpdated(updated: Project) {
    projects = projects.map((p) => (p.id === updated.id ? updated : p));
  }

  $effect(() => {
    const orgId = authState.activeOrganizationId;
    // refreshDashboard reads/writes `projects` synchronously before its
    // first await; without untrack, that read gets tracked as a dependency
    // of this effect, and the later write to `projects` re-fires it,
    // causing an unbounded refetch loop.
    untrack(() => {
      // No organization selected: there is nothing org-scoped to fetch, and
      // the UI renders a dedicated empty state instead of the registry. Skip
      // the subscription/fetch entirely rather than forwarding `null` to the
      // API layer.
      if (orgId == null) {
        unsubscribeProjects?.();
        unsubscribeProjects = null;
        isLoading = false;
        isRefreshing = false;
        return;
      }

      // The cache subscription is keyed by org (see EntityCacheStore.subscribe
      // in lib/cache.ts) -- it must be re-created whenever the active org
      // changes, or it stays locked to whichever org was active when it was
      // first created (e.g. null/"all" before the profile even finished
      // loading) and later notifications for that stale key (like the
      // unfiltered prefetchAll() list) silently overwrite the correctly
      // org-scoped `projects` state.
      unsubscribeProjects?.();
      unsubscribeProjects = projectsApi.subscribe((updatedProjects) => {
        projects = updatedProjects;
      }, orgId);
      refreshDashboard(true);
    });
  });

  async function refreshDashboard(force = false) {
    // Defense-in-depth for callers other than the $effect above (e.g.
    // handleBulkUpdated) — never fetch with no organization selected.
    if (authState.activeOrganizationId == null) {
      isLoading = false;
      isRefreshing = false;
      return;
    }

    if (!cachedStats && !projects.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }

    // Successive org switches each kick off their own refreshDashboard call;
    // their responses can resolve out of order over the network, so the org
    // this particular call was fetching for must be checked against the
    // still-current org before applying its result -- otherwise a slower,
    // now-stale response for a previously active org can land after (and
    // overwrite) the correct, current org's data.
    const requestOrgId = authState.activeOrganizationId;

    try {
      const [statsData, projectsData] = await Promise.all([
        dashboardApi.getStats({ forceRefresh: force, organization_id: requestOrgId }),
        projectsApi.list({ forceRefresh: force, organization_id: requestOrgId }),
      ]);
      if (authState.activeOrganizationId !== requestOrgId) return;
      stats = statsData;
      projects = projectsData.projects || [];
    } catch {
      // Keep cached or fallback
    } finally {
      if (authState.activeOrganizationId === requestOrgId) {
        isLoading = false;
        isRefreshing = false;
      }
    }
  }

  onMount(() => {
    // Subscription + initial fetch are handled by the $effect above, which
    // runs immediately on mount (activeOrganizationId is a dependency).

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
  />

  {#if authState.activeOrganizationId == null}
    <EmptyState
      icon={Building2}
      title="No organization selected"
      description="Select an organization to view its projects."
    />
  {:else}
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

  <!-- Project Registry -->
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold tracking-tight text-slate-50">Project Registry</h2>
        <p class="text-xs text-slate-400">
          Manage OpenBIM projects and jump directly to 3D visualization or compliance analysis.
        </p>
      </div>
    </div>

    {#if error}
      <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
        {error}
      </div>
    {/if}

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
          class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-hidden"
        />
      </div>

      <div class="flex w-full items-center gap-2 md:w-auto">
        <select
          bind:value={table.filters.status}
          class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
        >
          <option value="all">All Statuses</option>
          <option value="Active">Active</option>
          <option value="Draft">Draft</option>
          <option value="Archived">Archived</option>
        </select>

        <select
          bind:value={table.filters.domain}
          class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
        >
          <option value="all">All Domains</option>
          <option value="Arch">Arch</option>
          <option value="Piping">Piping</option>
          <option value="seismic">Seismic</option>
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
                      class="inline-block rounded px-2 py-0.5 font-mono text-micro font-semibold {getDomainBadgeClasses(
                        project.analysis_type,
                      )}"
                    >
                      {formatAnalysisDomain(project.analysis_type)}
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
  </div>
  {/if}
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
