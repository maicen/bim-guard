<script lang="ts">
  import {
    ShieldCheck,
    Save,
    CheckCircle2,
    XCircle,
    Building2,
    Filter,
    Lock,
    Users,
    FolderGit2,
    Share2,
    Settings,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import ProjectGroupAccessModal from "../lib/components/ProjectGroupAccessModal.svelte";
  import { organizationsApi, projectsApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { Group, OrganizationSummary, Project } from "../lib/types";

  let isSuperadmin = $derived(authState.isSuperadmin);

  let orgs = $state.raw<OrganizationSummary[]>([]);
  let projects = $state.raw<Project[]>([]);
  let crossOrgGrants = $state.raw<Record<number, Set<number>>>({});
  let groups = $state.raw<Group[]>([]);
  let groupGrants = $state.raw<Record<number, Set<number>>>({}); // groupId -> Set of projectIds
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
  let bulkTargetGroupId = $state<number | "all">("all");

  // Project modal for group access
  let managingProject = $state<Project | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      let loadedOrgs: OrganizationSummary[] = [];
      if (authState.isSuperadmin) {
        const orgRes = await organizationsApi.listAll();
        loadedOrgs = orgRes.organizations;
      } else {
        const myOrgs = authState.profile?.organizations ?? [];
        loadedOrgs = myOrgs.map((o) => ({
          id: o.organization_id,
          name: o.name,
          slug: o.slug,
        }));
      }
      orgs = loadedOrgs;

      const projectRes = await projectsApi.list();
      projects = projectRes.projects;

      // Cross-organization grants
      const nextGrants: Record<number, Set<number>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          try {
            const res = await organizationsApi.getProjectGrants(org.id);
            nextGrants[org.id] = new SvelteSet(res.project_ids);
          } catch {
            nextGrants[org.id] = new SvelteSet();
          }
        }),
      );
      crossOrgGrants = nextGrants;

      // Determine active organization
      let effectiveOrgId = authState.activeOrganizationId;
      if (!effectiveOrgId || !orgs.some((o) => o.id === effectiveOrgId)) {
        effectiveOrgId = orgs[0]?.id ?? 1;
      }
      if (!isSuperadmin) {
        selectedOrgFilter = effectiveOrgId;
      }
      bulkTargetOrgId = effectiveOrgId;

      await loadGroupsForOrg(effectiveOrgId);

      dirty.clear();
      selectedProjectIds.clear();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  async function loadGroupsForOrg(orgId: number) {
    try {
      const groupRes = await organizationsApi.listGroups(orgId);
      groups = groupRes.groups;
      if (groups.length > 0) {
        bulkTargetGroupId = groups[0]!.id;
      }

      const nextGroupGrants: Record<number, Set<number>> = {};
      await Promise.all(
        groups.map(async (group) => {
          try {
            const res = await organizationsApi.getGroupProjectGrants(orgId, group.id);
            nextGroupGrants[group.id] = new SvelteSet(res.project_ids);
          } catch {
            nextGroupGrants[group.id] = new SvelteSet();
          }
        }),
      );
      groupGrants = nextGroupGrants;
    } catch {
      groups = [];
      groupGrants = {};
    }
  }

  load();

  let displayOrgs = $derived(
    selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter),
  );

  let currentTargetOrg = $derived(displayOrgs[0] || orgs[0]);

  let hasActiveFilters = $derived(
    searchQuery.trim() !== "" ||
      selectedOrgFilter !== (isSuperadmin ? "all" : (authState.activeOrganizationId || (orgs[0]?.id ?? "all"))) ||
      grantStatusFilter !== "all",
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

      // Scope to caller's org if not superadmin
      if (!isSuperadmin && currentTargetOrg) {
        const isOwner = p.organization_id === currentTargetOrg.id || (!p.organization_id && currentTargetOrg.id === 1);
        const isGranted = crossOrgGrants[currentTargetOrg.id]?.has(p.id) ?? false;
        if (!isOwner && !isGranted) return false;
      }

      if (grantStatusFilter === "all") return true;

      const checkOrgs = selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter);
      const isGrantedAny = checkOrgs.some((o) => crossOrgGrants[o.id]?.has(p.id) || p.organization_id === o.id);

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
    if (isSuperadmin) {
      selectedOrgFilter = "all";
    } else {
      selectedOrgFilter = authState.activeOrganizationId || (orgs[0]?.id ?? "all");
    }
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
    if (!isSuperadmin) return;
    const orgSet = crossOrgGrants[orgId];
    if (!orgSet) return;
    if (orgSet.has(projectId)) orgSet.delete(projectId);
    else orgSet.add(projectId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
    if (!isSuperadmin) return;
    savingOrgId = orgId;
    try {
      await organizationsApi.setProjectGrants(orgId, Array.from(crossOrgGrants[orgId] ?? []));
      dirty.delete(orgId);
      toasts.success("Project access updated.");
    } catch (err) {
      toasts.fromError(err, "Could not save project access.");
    } finally {
      savingOrgId = null;
    }
  }

  async function saveAllDirty() {
    if (!isSuperadmin || dirty.size === 0) return;
    isSavingAll = true;
    try {
      for (const orgId of Array.from(dirty)) {
        await organizationsApi.setProjectGrants(orgId, Array.from(crossOrgGrants[orgId] ?? []));
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
    if (!isSuperadmin) return;
    const targetOrgIds =
      bulkTargetOrgId === "all" ? orgs.map((o) => o.id) : [Number(bulkTargetOrgId)];
    for (const orgId of targetOrgIds) {
      const orgSet = crossOrgGrants[orgId];
      if (!orgSet) continue;
      for (const projectId of selectedProjectIds) {
        const proj = projects.find((p) => p.id === projectId);
        if (proj && proj.organization_id === orgId) continue;
        orgSet.add(projectId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Granted ${selectedProjectIds.size} project(s). Click Save to persist.`);
  }

  function handleBulkRevoke() {
    if (!isSuperadmin) return;
    const targetOrgIds =
      bulkTargetOrgId === "all" ? orgs.map((o) => o.id) : [Number(bulkTargetOrgId)];
    for (const orgId of targetOrgIds) {
      const orgSet = crossOrgGrants[orgId];
      if (!orgSet) continue;
      for (const projectId of selectedProjectIds) {
        orgSet.delete(projectId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Revoked ${selectedProjectIds.size} project(s). Click Save to persist.`);
  }

  // Bulk assign group access for Organization Owner
  async function handleBulkAssignGroup() {
    if (bulkTargetGroupId === "all" || !currentTargetOrg) return;
    const targetGroupId = Number(bulkTargetGroupId);
    try {
      const currentSet = groupGrants[targetGroupId] ?? new Set();
      for (const pId of selectedProjectIds) {
        currentSet.add(pId);
      }
      await organizationsApi.setGroupProjectGrants(
        currentTargetOrg.id,
        targetGroupId,
        Array.from(currentSet),
      );
      toasts.success(`Assigned ${selectedProjectIds.size} project(s) to group.`);
      await loadGroupsForOrg(currentTargetOrg.id);
    } catch (err) {
      toasts.fromError(err, "Failed to assign projects to group.");
    }
  }

  function exportSelectedProjects() {
    const selectedList = projects.filter((p) => selectedProjectIds.has(p.id));
    const csvContent =
      "data:text/csv;charset=utf-8," +
      ["Project ID,Name,Country,Analysis Type,Organization ID"]
        .concat(
          selectedList.map(
            (p) =>
              `"${p.id}","${p.name}","${p.country || ""}","${p.analysis_type || ""}","${p.organization_id ?? ""}"`,
          ),
        )
        .join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `projects-access-export-${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toasts.success(`Exported ${selectedList.length} project(s) to CSV.`);
  }

  // Helper to get group names assigned to a project
  function getAssignedGroupsForProject(projectId: number): string[] {
    const assigned: string[] = [];
    for (const group of groups) {
      if (groupGrants[group.id]?.has(projectId)) {
        assigned.push(group.name);
      }
    }
    return assigned;
  }
</script>

<div class="space-y-6">
  <PageHeader
    category={isSuperadmin ? "Platform Governance" : "Organization Governance"}
    title="Project Access"
    subtitle={isSuperadmin
      ? "Cross-organization project sharing — which organizations may access projects across tenant boundaries."
      : "Manage internal group permissions and team access to projects within your organization."}
    icon={FolderGit2}
  >
    {#snippet actions()}
      {#if isSuperadmin && dirty.size > 0}
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

  <!-- Standardized Data Table Header with Filters & Search -->
  <DataTableHeader
    bind:searchQuery
    searchPlaceholder="Search projects by name, ID, country…"
    selectedCount={selectedProjectIds.size}
    selectedLabel="project"
    onClearSelection={() => selectedProjectIds.clear()}
    {hasActiveFilters}
    onResetFilters={resetFilters}
  >
    {#snippet filters()}
      <!-- Organization Selector -->
      {#if orgs.length > 1 || isSuperadmin}
        <div class="relative">
          <select
            bind:value={selectedOrgFilter}
            onchange={() => {
              if (selectedOrgFilter !== "all") {
                loadGroupsForOrg(Number(selectedOrgFilter));
              }
            }}
            aria-label="Filter by Organization"
            class="cursor-pointer appearance-none rounded-xl border border-slate-700 bg-slate-950 py-2 pl-3 pr-8 text-xs font-medium text-slate-300 focus:border-violet-500 focus:outline-none"
          >
            {#if isSuperadmin}
              <option value="all">All Organizations ({orgs.length})</option>
            {/if}
            {#each orgs as org (org.id)}
              <option value={org.id}>{org.name}</option>
            {/each}
          </select>
          <Building2 class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
        </div>
      {/if}

      <!-- Grant Status Filter -->
      <div class="relative">
        <select
          bind:value={grantStatusFilter}
          aria-label="Filter by Grant Status"
          class="cursor-pointer appearance-none rounded-xl border border-slate-700 bg-slate-950 py-2 pl-3 pr-8 text-xs font-medium text-slate-300 focus:border-violet-500 focus:outline-none"
        >
          <option value="all">All Access</option>
          <option value="granted">Granted / Owned</option>
          <option value="ungranted">Not Shared</option>
        </select>
        <Filter class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
      </div>
    {/snippet}
  </DataTableHeader>

  {#if loading}
    <LoadingState message="Loading organizations and projects…" />
  {:else if error}
    <EmptyState title="Could not load project access" description={error} icon={FolderGit2} />
  {:else if orgs.length === 0 || projects.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Project access requires at least one organization and one project."
      icon={FolderGit2}
    />
  {:else if filteredProjects.length === 0}
    <EmptyState
      title="No matching projects"
      description="Try clearing your search query or adjusting filters."
      icon={FolderGit2}
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

              <!-- Superadmin Multi-Org Columns -->
              {#if isSuperadmin && displayOrgs.length > 1}
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
              {:else}
                <!-- Organization Owner Columns: Ownership Type, Group Access, Manage -->
                <th class="min-w-[8rem] px-4 py-3">Ownership</th>
                <th class="min-w-[14rem] px-4 py-3">Group Access (RBAC)</th>
                <th class="w-24 px-4 py-3 text-center">Manage</th>
              {/if}
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each paginatedProjects as project (project.id)}
              {@const isRowSelected = selectedProjectIds.has(project.id)}
              {@const assignedGroups = getAssignedGroupsForProject(project.id)}
              {@const isOwner = currentTargetOrg ? (project.organization_id === currentTargetOrg.id || (!project.organization_id && currentTargetOrg.id === 1)) : false}
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

                <!-- Superadmin Multi-Org Sharing Matrix -->
                {#if isSuperadmin && displayOrgs.length > 1}
                  {#each displayOrgs as org (org.id)}
                    {@const isOrgOwner = project.organization_id === org.id || (!project.organization_id && org.id === 1)}
                    {@const isGranted = isOrgOwner || (crossOrgGrants[org.id]?.has(project.id) ?? false)}
                    <td class="px-4 py-3 text-center">
                      {#if isOrgOwner}
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
                {:else}
                  <!-- Org Owner View: Ownership Badge -->
                  <td class="px-4 py-3">
                    {#if isOwner}
                      <span class="inline-flex items-center gap-1 rounded-md border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-micro font-semibold text-blue-300">
                        <Lock class="h-3 w-3 text-blue-400" />
                        <span>Owned</span>
                      </span>
                    {:else}
                      <span class="inline-flex items-center gap-1 rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-micro font-semibold text-violet-300">
                        <Share2 class="h-3 w-3 text-violet-400" />
                        <span>Shared</span>
                      </span>
                    {/if}
                  </td>

                  <!-- Org Owner View: Assigned Group Badges -->
                  <td class="px-4 py-3">
                    {#if assignedGroups.length > 0}
                      <div class="flex flex-wrap gap-1">
                        {#each assignedGroups as groupName}
                          <span class="inline-flex items-center gap-1 rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-micro font-medium text-violet-300">
                            <Users class="h-3 w-3 text-violet-400" />
                            <span>{groupName}</span>
                          </span>
                        {/each}
                      </div>
                    {:else}
                      <span class="text-micro text-slate-500 italic">All organization members (no group gating)</span>
                    {/if}
                  </td>

                  <!-- Org Owner View: Manage Action Button -->
                  <td class="px-4 py-3 text-center">
                    <button
                      type="button"
                      onclick={() => (managingProject = project)}
                      class="inline-flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1 text-micro font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
                      title="Manage internal group access"
                    >
                      <Settings class="h-3 w-3 text-slate-400" />
                      <span>Groups</span>
                    </button>
                  </td>
                {/if}
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
    onBulkExport={exportSelectedProjects}
  >
    {#if isSuperadmin}
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
    {:else if groups.length > 0}
      <!-- Org Owner: Bulk Assign Group Access -->
      <div class="flex items-center gap-2">
        <span class="text-micro text-violet-300 font-medium">Assign to Group:</span>
        <select
          bind:value={bulkTargetGroupId}
          aria-label="Target Group for Bulk Action"
          class="cursor-pointer appearance-none rounded-lg border border-slate-700 bg-slate-900 py-1 pl-2.5 pr-6 text-xs text-slate-200 focus:outline-none"
        >
          {#each groups as grp (grp.id)}
            <option value={grp.id}>{grp.name}</option>
          {/each}
        </select>
        <button
          type="button"
          onclick={handleBulkAssignGroup}
          class="rounded-lg bg-violet-600 px-2.5 py-1 text-xs font-semibold text-white shadow hover:bg-violet-500"
        >
          Assign Group
        </button>
      </div>
    {/if}
  </BulkActionBar>

  <!-- Project Group Access Modal -->
  {#if currentTargetOrg}
    <ProjectGroupAccessModal
      open={managingProject !== null}
      project={managingProject}
      organizationId={currentTargetOrg.id}
      {groups}
      onClose={() => (managingProject = null)}
      onSaved={() => currentTargetOrg && loadGroupsForOrg(currentTargetOrg.id)}
    />
  {/if}
</div>
