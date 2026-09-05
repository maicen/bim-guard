<script lang="ts">
  import {
    ShieldCheck,
    Save,
    Search,
    RotateCcw,
    CheckCircle2,
    XCircle,
    Building2,
    Filter,
    Lock,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import { organizationsApi, projectsApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { OrganizationSummary, Project } from "../lib/types";

  let orgs = $state.raw<OrganizationSummary[]>([]);
  let projects = $state.raw<Project[]>([]);
  let grants = $state.raw<Record<number, Set<number>>>({});
  const dirty: Set<number> = new SvelteSet();
  let loading = $state(true);
  let error = $state<string | null>(null);
  let savingOrgId = $state<number | null>(null);
  let isSavingAll = $state(false);

  // Table state: search, filter, sort, pagination, selection
  let searchQuery = $state("");
  let selectedOrgFilter = $state<number | "all">("all");
  let grantStatusFilter = $state<"all" | "granted" | "ungranted">("all");
  let sortField = $state<"name" | "id" | "country">("name");
  let sortAsc = $state(true);
  let pageIndex = $state(1);
  let pageSize = $state(10);
  const selectedProjectIds: Set<number> = new SvelteSet();

  let bulkTargetOrgId = $state<number | "all">("all");

  async function load() {
    loading = true;
    error = null;
    try {
      const [orgRes, projectRes] = await Promise.all([organizationsApi.listAll(), projectsApi.list()]);
      orgs = orgRes.organizations;
      projects = projectRes.projects;
      const nextGrants: Record<number, Set<number>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          const res = await organizationsApi.getProjectGrants(org.id);
          nextGrants[org.id] = new SvelteSet(res.project_ids);
        }),
      );
      grants = nextGrants;
      dirty.clear();
      selectedProjectIds.clear();
      if (orgs.length > 0 && bulkTargetOrgId === "all") {
        bulkTargetOrgId = orgs[0]!.id;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  load();

  let displayOrgs = $derived(
    selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter),
  );

  let filteredProjects = $derived(
    projects.filter((p) => {
      const q = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !q ||
        p.name.toLowerCase().includes(q) ||
        String(p.id).includes(q) ||
        (p.country && p.country.toLowerCase().includes(q));

      if (!matchesSearch) return false;

      if (grantStatusFilter === "all") return true;

      const checkOrgs = selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter);
      const isGrantedAny = checkOrgs.some((o) => grants[o.id]?.has(p.id) || p.organization_id === o.id);

      if (grantStatusFilter === "granted") return isGrantedAny;
      if (grantStatusFilter === "ungranted") return !isGrantedAny;

      return true;
    }),
  );

  let sortedProjects = $derived.by(() => {
    const dir = sortAsc ? 1 : -1;
    return [...filteredProjects].sort((a, b) => {
      if (sortField === "name") {
        return a.name.localeCompare(b.name) * dir;
      }
      if (sortField === "country") {
        return (a.country || "").localeCompare(b.country || "") * dir;
      }
      return (a.id - b.id) * dir;
    });
  });

  let paginatedProjects = $derived(
    sortedProjects.slice((pageIndex - 1) * pageSize, pageIndex * pageSize),
  );

  function handleSort(col: "name" | "id" | "country") {
    if (sortField === col) {
      sortAsc = !sortAsc;
    } else {
      sortField = col;
      sortAsc = true;
    }
  }

  function resetFilters() {
    searchQuery = "";
    selectedOrgFilter = "all";
    grantStatusFilter = "all";
    pageIndex = 1;
  }

  function toggleSelectRow(projectId: number) {
    if (selectedProjectIds.has(projectId)) {
      selectedProjectIds.delete(projectId);
    } else {
      selectedProjectIds.add(projectId);
    }
  }

  function toggleSelectAll() {
    const pageIds = paginatedProjects.map((p) => p.id);
    const allSelected = pageIds.every((id) => selectedProjectIds.has(id));
    for (const id of pageIds) {
      if (allSelected) selectedProjectIds.delete(id);
      else selectedProjectIds.add(id);
    }
  }

  let allOnPageSelected = $derived(
    paginatedProjects.length > 0 &&
      paginatedProjects.every((p) => selectedProjectIds.has(p.id)),
  );
  let someOnPageSelected = $derived(
    paginatedProjects.some((p) => selectedProjectIds.has(p.id)) && !allOnPageSelected,
  );

  function toggleGrant(orgId: number, projectId: number) {
    const orgGrants = grants[orgId];
    if (!orgGrants) return;
    if (orgGrants.has(projectId)) orgGrants.delete(projectId);
    else orgGrants.add(projectId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
    savingOrgId = orgId;
    try {
      await organizationsApi.setProjectGrants(orgId, Array.from(grants[orgId] ?? []));
      dirty.delete(orgId);
      toasts.success("Project access updated.");
    } catch (err) {
      toasts.fromError(err, "Could not save project access.");
    } finally {
      savingOrgId = null;
    }
  }

  async function saveAllDirty() {
    if (dirty.size === 0) return;
    isSavingAll = true;
    try {
      for (const orgId of Array.from(dirty)) {
        await organizationsApi.setProjectGrants(orgId, Array.from(grants[orgId] ?? []));
        dirty.delete(orgId);
      }
      toasts.success("All organization project grants saved.");
    } catch (err) {
      toasts.fromError(err, "Failed saving some changes.");
    } finally {
      isSavingAll = false;
    }
  }

  function handleBulkGrant() {
    const targetOrgIds =
      bulkTargetOrgId === "all" ? orgs.map((o) => o.id) : [Number(bulkTargetOrgId)];
    for (const orgId of targetOrgIds) {
      const orgSet = grants[orgId];
      if (!orgSet) continue;
      for (const projectId of selectedProjectIds) {
        // Do not grant to owner (it already owns it)
        const proj = projects.find((p) => p.id === projectId);
        if (proj && proj.organization_id === orgId) continue;
        orgSet.add(projectId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Granted ${selectedProjectIds.size} project(s). Click Save to persist.`);
  }

  function handleBulkRevoke() {
    const targetOrgIds =
      bulkTargetOrgId === "all" ? orgs.map((o) => o.id) : [Number(bulkTargetOrgId)];
    for (const orgId of targetOrgIds) {
      const orgSet = grants[orgId];
      if (!orgSet) continue;
      for (const projectId of selectedProjectIds) {
        orgSet.delete(projectId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Revoked ${selectedProjectIds.size} project(s). Click Save to persist.`);
  }
</script>

<div class="space-y-6">
  <PageHeader
    category="Administration"
    title="Project Access"
    subtitle="Cross-org project sharing — which other organizations (beyond the project owner) may access each project."
    icon={ShieldCheck}
  >
    {#snippet actions()}
      {#if dirty.size > 0}
        <button
          type="button"
          onclick={saveAllDirty}
          disabled={isSavingAll}
          class="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-violet-600/30 transition-all hover:bg-violet-500 disabled:opacity-50"
        >
          <Save class="h-4 w-4" />
          <span>{isSavingAll ? "Saving…" : `Save All Changes (${dirty.size} pending)`}</span>
        </button>
      {/if}
    {/snippet}
  </PageHeader>

  <!-- Controls Bar -->
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
    <div class="flex flex-1 flex-wrap items-center gap-3">
      <!-- Search -->
      <div class="relative min-w-[16rem] flex-1 max-w-md">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Search projects by name, ID, country…"
          bind:value={searchQuery}
          class="w-full rounded-xl border border-slate-700 bg-slate-950 py-2 pl-9 pr-4 text-xs text-slate-200 placeholder-slate-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
        />
      </div>

      <!-- Organization Filter -->
      <div class="relative">
        <select
          bind:value={selectedOrgFilter}
          aria-label="Filter by Organization"
          class="cursor-pointer appearance-none rounded-xl border border-slate-700 bg-slate-950 py-2 pl-3 pr-8 text-xs font-medium text-slate-300 focus:border-violet-500 focus:outline-none"
        >
          <option value="all">All Organizations ({orgs.length})</option>
          {#each orgs as org (org.id)}
            <option value={org.id}>{org.name}</option>
          {/each}
        </select>
        <Building2 class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
      </div>

      <!-- Grant Status Filter -->
      <div class="relative">
        <select
          bind:value={grantStatusFilter}
          aria-label="Filter by Grant Status"
          class="cursor-pointer appearance-none rounded-xl border border-slate-700 bg-slate-950 py-2 pl-3 pr-8 text-xs font-medium text-slate-300 focus:border-violet-500 focus:outline-none"
        >
          <option value="all">All Statuses</option>
          <option value="granted">Granted / Owned</option>
          <option value="ungranted">Not Shared</option>
        </select>
        <Filter class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
      </div>

      {#if searchQuery || selectedOrgFilter !== "all" || grantStatusFilter !== "all"}
        <button
          type="button"
          onclick={resetFilters}
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-slate-700"
        >
          <RotateCcw class="h-3.5 w-3.5" />
          <span>Reset</span>
        </button>
      {/if}
    </div>

    {#if selectedProjectIds.size > 0}
      <div class="flex items-center gap-2 text-xs text-violet-300">
        <span class="font-semibold">{selectedProjectIds.size}</span> project(s) selected
        <button
          type="button"
          onclick={() => selectedProjectIds.clear()}
          class="text-micro underline text-slate-400 hover:text-slate-200 ml-1"
        >
          Clear
        </button>
      </div>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Loading organizations and projects…" />
  {:else if error}
    <EmptyState title="Could not load project access" description={error} icon={ShieldCheck} />
  {:else if orgs.length === 0 || projects.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Project access requires at least one organization and one project."
      icon={ShieldCheck}
    />
  {:else if filteredProjects.length === 0}
    <EmptyState
      title="No matching projects"
      description="Try clearing your search query or adjusting filters."
      icon={ShieldCheck}
      actionLabel="Reset Filters"
      onAction={resetFilters}
    />
  {:else}
    <!-- Data Table Container -->
    <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40 shadow-xl">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/80">
              <th class="w-12 px-4 py-3 text-center">
                <TableCheckbox
                  checked={allOnPageSelected}
                  indeterminate={someOnPageSelected}
                  onchange={toggleSelectAll}
                  ariaLabel="Select all projects on page"
                />
              </th>
              <SortHeader
                column="name"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("name")}
                customClass="min-w-[16rem] px-4 py-3"
              >
                Project Name
              </SortHeader>
              <SortHeader
                column="country"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("country")}
                customClass="min-w-[8rem] px-4 py-3"
              >
                Country
              </SortHeader>
              {#each displayOrgs as org (org.id)}
                <th class="min-w-[11rem] px-4 py-3 text-center">
                  <div class="truncate font-semibold text-slate-100" title={org.name}>
                    {org.name}
                  </div>
                  <button
                    type="button"
                    disabled={!dirty.has(org.id) || savingOrgId === org.id}
                    onclick={() => saveOrg(org.id)}
                    class="mt-1 inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-2 py-0.5 text-micro font-medium text-slate-300 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <Save class="h-3 w-3" />
                    <span>{savingOrgId === org.id ? "Saving…" : dirty.has(org.id) ? "Save" : "Saved"}</span>
                  </button>
                </th>
              {/each}
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each paginatedProjects as project (project.id)}
              {@const isRowSelected = selectedProjectIds.has(project.id)}
              <tr
                class="transition-colors hover:bg-slate-800/40 {isRowSelected ? 'bg-violet-950/20' : ''}"
              >
                <td class="px-4 py-3 text-center">
                  <TableCheckbox
                    checked={isRowSelected}
                    onchange={() => toggleSelectRow(project.id)}
                    ariaLabel={`Select ${project.name}`}
                  />
                </td>
                <td class="px-4 py-3 font-medium text-slate-200">
                  <div class="truncate font-semibold text-slate-100" title={project.name}>
                    {project.name}
                  </div>
                  <div class="text-micro text-slate-500 font-mono">
                    #{project.id} &middot; {project.analysis_type || "Arch"}
                  </div>
                </td>
                <td class="px-4 py-3 text-slate-400">
                  {project.country || "—"}
                </td>
                {#each displayOrgs as org (org.id)}
                  {@const isOwner = project.organization_id === org.id || (!project.organization_id && org.id === 1)}
                  {@const isGranted = isOwner || (grants[org.id]?.has(project.id) ?? false)}
                  <td class="px-4 py-3 text-center">
                    {#if isOwner}
                      <span
                        class="inline-flex items-center gap-1 rounded-lg border border-blue-500/30 bg-blue-500/10 px-2.5 py-1 text-micro font-semibold text-blue-300"
                        title="Owning Organization (Primary owner)"
                      >
                        <Lock class="h-3 w-3 text-blue-400" />
                        <span>Owner</span>
                      </span>
                    {:else}
                      <button
                        type="button"
                        onclick={() => toggleGrant(org.id, project.id)}
                        class="group inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-all {isGranted
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                          : 'border-slate-700 bg-slate-800/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'}"
                        title={isGranted ? `Revoke access from ${org.name}` : `Grant access to ${org.name}`}
                      >
                        {#if isGranted}
                          <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                          <span>Granted</span>
                        {:else}
                          <XCircle class="h-3.5 w-3.5 text-slate-500 group-hover:text-slate-400" />
                          <span>No Access</span>
                        {/if}
                      </button>
                    {/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <TablePagination
        totalItems={sortedProjects.length}
        {pageSize}
        currentPage={pageIndex}
        onPageChange={(p) => (pageIndex = p)}
        onPageSizeChange={(s) => {
          pageSize = s;
          pageIndex = 1;
        }}
      />
    </div>
  {/if}

  <!-- Bulk Action Bar -->
  <BulkActionBar
    selectedCount={selectedProjectIds.size}
    itemLabel="project"
    onClearSelection={() => selectedProjectIds.clear()}
  >
    <div class="flex items-center gap-2">
      <select
        bind:value={bulkTargetOrgId}
        aria-label="Target Organization for Bulk Action"
        class="cursor-pointer appearance-none rounded-lg border border-slate-700 bg-slate-900 py-1 pl-2.5 pr-6 text-xs text-slate-200 focus:outline-none"
      >
        <option value="all">All Organizations</option>
        {#each orgs as org (org.id)}
          <option value={org.id}>{org.name}</option>
        {/each}
      </select>
      <button
        type="button"
        onclick={handleBulkGrant}
        class="rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white shadow hover:bg-emerald-500"
      >
        Grant Access
      </button>
      <button
        type="button"
        onclick={handleBulkRevoke}
        class="rounded-lg bg-rose-600 px-2.5 py-1 text-xs font-semibold text-white shadow hover:bg-rose-500"
      >
        Revoke Access
      </button>
    </div>
  </BulkActionBar>
</div>
