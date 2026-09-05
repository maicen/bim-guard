<script lang="ts">
  import {
    ShieldCheck,
    Save,
    CheckCircle2,
    XCircle,
    Building2,
    Filter,
    Eye,
    Layers,
    Info,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import RulesetDetailsModal from "../lib/components/RulesetDetailsModal.svelte";
  import { organizationsApi, rulesApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { OrganizationSummary, RuleFolder } from "../lib/types";

  let isSuperadmin = $derived(authState.isSuperadmin);

  let orgs = $state.raw<OrganizationSummary[]>([]);
  let rulesets = $state.raw<RuleFolder[]>([]);
  let grants = $state.raw<Record<number, Set<string>>>({});
  const dirty: Set<number> = new SvelteSet();
  let loading = $state(true);
  let error = $state<string | null>(null);
  let savingOrgId = $state<number | null>(null);
  let isSavingAll = $state(false);

  // Table state: search, filter, sort, pagination, selection
  let searchQuery = $state("");
  let selectedOrgFilter = $state<number | "all">("all");
  let categoryFilter = $state<string>("all");
  let grantStatusFilter = $state<"all" | "granted" | "ungranted">("all");
  let sortField = $state<"name" | "id" | "category" | "count">("name");
  let sortAsc = $state(true);
  let pageIndex = $state(1);
  let pageSize = $state(10);
  const selectedRulesetIds: Set<string> = new SvelteSet();

  // Target org for bulk grant/revoke
  let bulkTargetOrgId = $state<number | "all">("all");

  // Inspection modal
  let inspectingRuleset = $state<RuleFolder | null>(null);

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

      const folderRes = await rulesApi.folders();
      rulesets = folderRes;

      const nextGrants: Record<number, Set<string>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          try {
            const res = await organizationsApi.getRulesetGrants(org.id);
            nextGrants[org.id] = new SvelteSet(res.ruleset_ids);
          } catch {
            nextGrants[org.id] = new SvelteSet();
          }
        }),
      );
      grants = nextGrants;
      dirty.clear();
      selectedRulesetIds.clear();

      if (authState.activeOrganizationId && orgs.some((o) => o.id === authState.activeOrganizationId)) {
        selectedOrgFilter = authState.activeOrganizationId;
        bulkTargetOrgId = authState.activeOrganizationId;
      } else if (orgs.length > 0) {
        if (!isSuperadmin) selectedOrgFilter = orgs[0]!.id;
        bulkTargetOrgId = orgs[0]!.id;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  load();

  // Distinct categories from rulesets
  let categories = $derived(
    Array.from(new Set(rulesets.map((r) => r.category || "General"))).filter(Boolean),
  );

  // Active columns to display based on org filter
  let displayOrgs = $derived(
    selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter),
  );

  let hasActiveFilters = $derived(
    searchQuery.trim() !== "" ||
      selectedOrgFilter !== (isSuperadmin ? "all" : (authState.activeOrganizationId || (orgs[0]?.id ?? "all"))) ||
      categoryFilter !== "all" ||
      grantStatusFilter !== "all",
  );

  // Filtered rulesets
  let filteredRulesets = $derived(
    rulesets.filter((r) => {
      const q = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !q ||
        r.display_name.toLowerCase().includes(q) ||
        r.ruleset_id.toLowerCase().includes(q) ||
        (r.description && r.description.toLowerCase().includes(q));

      if (!matchesSearch) return false;

      if (categoryFilter !== "all" && (r.category || "General") !== categoryFilter) {
        return false;
      }

      if (grantStatusFilter === "all") return true;

      const checkOrgs = selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter);
      const isGrantedAny = checkOrgs.some((o) => grants[o.id]?.has(r.ruleset_id));

      if (grantStatusFilter === "granted") return isGrantedAny;
      if (grantStatusFilter === "ungranted") return !isGrantedAny;

      return true;
    }),
  );

  // Sorted rulesets
  let sortedRulesets = $derived.by(() => {
    const dir = sortAsc ? 1 : -1;
    return [...filteredRulesets].sort((a, b) => {
      if (sortField === "name") {
        return a.display_name.localeCompare(b.display_name) * dir;
      }
      if (sortField === "id") {
        return a.ruleset_id.localeCompare(b.ruleset_id) * dir;
      }
      if (sortField === "category") {
        return (a.category || "General").localeCompare(b.category || "General") * dir;
      }
      if (sortField === "count") {
        const countA = a.rules?.length || a.count || 0;
        const countB = b.rules?.length || b.count || 0;
        return (countA - countB) * dir;
      }
      return 0;
    });
  });

  // Paginated rulesets
  let paginatedRulesets = $derived(
    sortedRulesets.slice((pageIndex - 1) * pageSize, pageIndex * pageSize),
  );

  function handleSort(col: "name" | "id" | "category" | "count") {
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
    categoryFilter = "all";
    grantStatusFilter = "all";
    pageIndex = 1;
  }

  // Row selection
  function toggleSelectRow(rulesetId: string) {
    if (selectedRulesetIds.has(rulesetId)) {
      selectedRulesetIds.delete(rulesetId);
    } else {
      selectedRulesetIds.add(rulesetId);
    }
  }

  function toggleSelectAll() {
    const pageIds = paginatedRulesets.map((r) => r.ruleset_id);
    const allSelected = pageIds.every((id) => selectedRulesetIds.has(id));
    for (const id of pageIds) {
      if (allSelected) selectedRulesetIds.delete(id);
      else selectedRulesetIds.add(id);
    }
  }

  let allOnPageSelected = $derived(
    paginatedRulesets.length > 0 &&
      paginatedRulesets.every((r) => selectedRulesetIds.has(r.ruleset_id)),
  );
  let someOnPageSelected = $derived(
    paginatedRulesets.some((r) => selectedRulesetIds.has(r.ruleset_id)) && !allOnPageSelected,
  );

  function toggleGrant(orgId: number, rulesetId: string) {
    if (!isSuperadmin) return;
    const orgGrants = grants[orgId];
    if (!orgGrants) return;
    if (orgGrants.has(rulesetId)) orgGrants.delete(rulesetId);
    else orgGrants.add(rulesetId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
    if (!isSuperadmin) return;
    savingOrgId = orgId;
    try {
      await organizationsApi.setRulesetGrants(orgId, Array.from(grants[orgId] ?? []));
      dirty.delete(orgId);
      toasts.success("Ruleset access updated.");
    } catch (err) {
      toasts.fromError(err, "Could not save ruleset access.");
    } finally {
      savingOrgId = null;
    }
  }

  async function saveAllDirty() {
    if (!isSuperadmin || dirty.size === 0) return;
    isSavingAll = true;
    try {
      for (const orgId of Array.from(dirty)) {
        await organizationsApi.setRulesetGrants(orgId, Array.from(grants[orgId] ?? []));
        dirty.delete(orgId);
      }
      toasts.success("All organization ruleset grants saved.");
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
      const orgSet = grants[orgId];
      if (!orgSet) continue;
      for (const rulesetId of selectedRulesetIds) {
        orgSet.add(rulesetId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Granted ${selectedRulesetIds.size} ruleset(s). Click Save to persist.`);
  }

  function handleBulkRevoke() {
    if (!isSuperadmin) return;
    const targetOrgIds =
      bulkTargetOrgId === "all" ? orgs.map((o) => o.id) : [Number(bulkTargetOrgId)];
    for (const orgId of targetOrgIds) {
      const orgSet = grants[orgId];
      if (!orgSet) continue;
      for (const rulesetId of selectedRulesetIds) {
        orgSet.delete(rulesetId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Revoked ${selectedRulesetIds.size} ruleset(s). Click Save to persist.`);
  }

  function exportSelectedRulesets() {
    const selectedList = rulesets.filter((r) => selectedRulesetIds.has(r.ruleset_id));
    const csvContent =
      "data:text/csv;charset=utf-8," +
      ["Ruleset ID,Display Name,Category,Rule Count,Description"]
        .concat(
          selectedList.map(
            (r) =>
              `"${r.ruleset_id}","${r.display_name}","${r.category || ""}","${r.rules?.length || r.count || 0}","${(r.description || "").replace(/"/g, '""')}"`,
          ),
        )
        .join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `rulesets-export-${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toasts.success(`Exported ${selectedList.length} ruleset(s) to CSV.`);
  }
</script>

<div class="space-y-6">
  <PageHeader
    category={isSuperadmin ? "Platform Governance" : "Organization Governance"}
    title="Ruleset Access"
    subtitle={isSuperadmin
      ? "Manage which engineering compliance rulesets each organization is granted to bind to its projects."
      : "Ruleset catalogs and active engineering compliance standards licensed for your organization."}
    icon={ShieldCheck}
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
    searchPlaceholder="Search rulesets by name, ID, or description…"
    selectedCount={selectedRulesetIds.size}
    selectedLabel="ruleset"
    onClearSelection={() => selectedRulesetIds.clear()}
    {hasActiveFilters}
    onResetFilters={resetFilters}
  >
    {#snippet filters()}
      <!-- Organization Selector -->
      {#if orgs.length > 1 || isSuperadmin}
        <div class="relative">
          <select
            bind:value={selectedOrgFilter}
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

      <!-- Category Filter -->
      <div class="relative">
        <select
          bind:value={categoryFilter}
          aria-label="Filter by Category"
          class="cursor-pointer appearance-none rounded-xl border border-slate-700 bg-slate-950 py-2 pl-3 pr-8 text-xs font-medium text-slate-300 focus:border-violet-500 focus:outline-none"
        >
          <option value="all">All Categories</option>
          {#each categories as cat}
            <option value={cat}>{cat}</option>
          {/each}
        </select>
        <Layers class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
      </div>

      <!-- Grant Status Filter -->
      <div class="relative">
        <select
          bind:value={grantStatusFilter}
          aria-label="Filter by Grant Status"
          class="cursor-pointer appearance-none rounded-xl border border-slate-700 bg-slate-950 py-2 pl-3 pr-8 text-xs font-medium text-slate-300 focus:border-violet-500 focus:outline-none"
        >
          <option value="all">All Statuses</option>
          <option value="granted">Granted Only</option>
          <option value="ungranted">Ungranted Only</option>
        </select>
        <Filter class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
      </div>
    {/snippet}
  </DataTableHeader>

  {#if loading}
    <LoadingState message="Loading organizations and ruleset catalog…" />
  {:else if error}
    <EmptyState title="Could not load ruleset access" description={error} icon={ShieldCheck} />
  {:else if orgs.length === 0 || rulesets.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Ruleset access requires at least one organization and active rule folder."
      icon={ShieldCheck}
    />
  {:else if filteredRulesets.length === 0}
    <EmptyState
      title="No matching rulesets"
      description="Try clearing your search query or adjusting organization/status filters."
      icon={ShieldCheck}
      actionLabel="Reset Filters"
      onAction={resetFilters}
    />
  {:else}
    <!-- Rich Data Table Container -->
    <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40 shadow-xl">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/80">
              <!-- Master Checkbox Column -->
              <th class="w-12 px-4 py-3 text-center">
                <TableCheckbox
                  checked={allOnPageSelected}
                  indeterminate={someOnPageSelected}
                  onchange={toggleSelectAll}
                  ariaLabel="Select all rulesets on page"
                />
              </th>

              <!-- Sortable Ruleset Name -->
              <SortHeader
                column="name"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("name")}
                customClass="min-w-[14rem] px-4 py-3"
              >
                Ruleset Name
              </SortHeader>

              <!-- Sortable Ruleset ID -->
              <SortHeader
                column="id"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("id")}
                customClass="min-w-[12rem] px-4 py-3"
              >
                Ruleset ID
              </SortHeader>

              <!-- Category -->
              <SortHeader
                column="category"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("category")}
                customClass="min-w-[9rem] px-4 py-3"
              >
                Category
              </SortHeader>

              <!-- Rules Count -->
              <SortHeader
                column="count"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("count")}
                customClass="min-w-[7rem] px-4 py-3 text-center"
                align="center"
              >
                Rules
              </SortHeader>

              <!-- Organization Grant Columns (Superadmin Multi-Org View) -->
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
                <!-- Single Org Access Status Column (Org Owner View or Single-Filtered Superadmin) -->
                {@const targetOrg = displayOrgs[0] || orgs[0]}
                <th class="min-w-[12rem] px-4 py-3 text-center">
                  <div class="font-semibold text-slate-100">
                    {targetOrg?.name || "Organization"} Access
                  </div>
                  {#if isSuperadmin && targetOrg && dirty.has(targetOrg.id)}
                    <button
                      type="button"
                      disabled={savingOrgId === targetOrg.id}
                      onclick={() => saveOrg(targetOrg.id)}
                      class="mt-1 inline-flex items-center gap-1 rounded-lg border border-violet-500/40 bg-violet-600/30 px-2.5 py-0.5 text-micro font-semibold text-violet-200 transition-colors hover:bg-violet-600/50"
                    >
                      <Save class="h-3 w-3" />
                      <span>{savingOrgId === targetOrg.id ? "Saving…" : "Save Changes"}</span>
                    </button>
                  {/if}
                </th>
              {/if}

              <!-- Actions Column -->
              <th class="w-16 px-4 py-3 text-center">Details</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each paginatedRulesets as ruleset (ruleset.ruleset_id)}
              {@const isRowSelected = selectedRulesetIds.has(ruleset.ruleset_id)}
              {@const singleOrg = displayOrgs[0] || orgs[0]}
              {@const isSingleOrgGranted = singleOrg ? (grants[singleOrg.id]?.has(ruleset.ruleset_id) ?? false) : false}
              <tr
                class="transition-colors hover:bg-slate-800/40 {isRowSelected ? 'bg-violet-950/20' : ''}"
              >
                <!-- Row Checkbox -->
                <td class="px-4 py-3 text-center">
                  <TableCheckbox
                    checked={isRowSelected}
                    onchange={() => toggleSelectRow(ruleset.ruleset_id)}
                    ariaLabel={`Select ${ruleset.display_name}`}
                  />
                </td>

                <!-- Ruleset Name -->
                <td class="px-4 py-3 font-medium text-slate-200">
                  <div class="truncate font-semibold text-slate-100" title={ruleset.display_name}>
                    {ruleset.display_name}
                  </div>
                  {#if ruleset.description}
                    <div class="truncate text-micro text-slate-400" title={ruleset.description}>
                      {ruleset.description}
                    </div>
                  {/if}
                </td>

                <!-- Ruleset ID -->
                <td class="px-4 py-3 font-mono text-micro text-slate-400">
                  <span class="rounded bg-slate-800/80 px-1.5 py-0.5 text-slate-300">
                    {ruleset.ruleset_id}
                  </span>
                </td>

                <!-- Category -->
                <td class="px-4 py-3">
                  <span class="rounded-lg border border-slate-800 bg-slate-900/60 px-2 py-0.5 text-micro font-medium text-slate-300">
                    {ruleset.category || "General"}
                  </span>
                </td>

                <!-- Rule Count -->
                <td class="px-4 py-3 text-center font-mono text-micro text-slate-300">
                  {ruleset.rules?.length || ruleset.count || 0}
                </td>

                <!-- Multi-Org Columns (Superadmin View) -->
                {#if isSuperadmin && displayOrgs.length > 1}
                  {#each displayOrgs as org (org.id)}
                    {@const isGranted = grants[org.id]?.has(ruleset.ruleset_id) ?? false}
                    <td class="px-4 py-3 text-center">
                      <button
                        type="button"
                        onclick={() => toggleGrant(org.id, ruleset.ruleset_id)}
                        class="group inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-semibold transition-all {isGranted
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                          : 'border-slate-700 bg-slate-800/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'}"
                        title={isGranted ? `Revoke from ${org.name}` : `Grant to ${org.name}`}
                      >
                        {#if isGranted}
                          <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                          <span>Granted</span>
                        {:else}
                          <XCircle class="h-3.5 w-3.5 text-slate-500 group-hover:text-slate-400" />
                          <span>No Access</span>
                        {/if}
                      </button>
                    </td>
                  {/each}
                {:else}
                  <!-- Single Org Status Row (Org Owner View or Single-Filtered Superadmin) -->
                  <td class="px-4 py-3 text-center">
                    {#if isSuperadmin && singleOrg}
                      <button
                        type="button"
                        onclick={() => toggleGrant(singleOrg.id, ruleset.ruleset_id)}
                        class="group inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-semibold transition-all {isSingleOrgGranted
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                          : 'border-slate-700 bg-slate-800/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'}"
                        title={isSingleOrgGranted ? `Click to revoke` : `Click to grant`}
                      >
                        {#if isSingleOrgGranted}
                          <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                          <span>Granted</span>
                        {:else}
                          <XCircle class="h-3.5 w-3.5 text-slate-500 group-hover:text-slate-400" />
                          <span>Not Granted</span>
                        {/if}
                      </button>
                    {:else}
                      <!-- Org Owner View: Clean Status Badge -->
                      {#if isSingleOrgGranted}
                        <span
                          class="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-300"
                        >
                          <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                          <span>Granted to Org</span>
                        </span>
                      {:else}
                        <span
                          class="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-xs font-medium text-slate-400"
                        >
                          <Info class="h-3.5 w-3.5 text-slate-500" />
                          <span>Catalog Standard</span>
                        </span>
                      {/if}
                    {/if}
                  </td>
                {/if}

                <!-- Inspect Button -->
                <td class="px-4 py-3 text-center">
                  <button
                    type="button"
                    onclick={() => (inspectingRuleset = ruleset)}
                    class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
                    title="Inspect ruleset rules and metadata"
                  >
                    <Eye class="h-4 w-4" />
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <TablePagination
        totalItems={sortedRulesets.length}
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
    selectedCount={selectedRulesetIds.size}
    itemLabel="ruleset"
    onClearSelection={() => selectedRulesetIds.clear()}
    onBulkExport={exportSelectedRulesets}
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
    {/if}
  </BulkActionBar>

  <!-- Inspection Modal -->
  <RulesetDetailsModal
    open={inspectingRuleset !== null}
    ruleset={inspectingRuleset}
    isGranted={inspectingRuleset && (displayOrgs[0] || orgs[0])
      ? (grants[(displayOrgs[0] || orgs[0])!.id]?.has(inspectingRuleset.ruleset_id) ?? false)
      : false}
    onClose={() => (inspectingRuleset = null)}
  />
</div>
