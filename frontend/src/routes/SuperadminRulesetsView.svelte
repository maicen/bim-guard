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
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import { organizationsApi, rulesApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { OrganizationSummary, RuleFolder } from "../lib/types";

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
  let grantStatusFilter = $state<"all" | "granted" | "ungranted">("all");
  let sortField = $state<"name" | "id">("name");
  let sortAsc = $state(true);
  let pageIndex = $state(1);
  let pageSize = $state(10);
  const selectedRulesetIds: Set<string> = new SvelteSet();

  // Target org for bulk grant/revoke
  let bulkTargetOrgId = $state<number | "all">("all");

  async function load() {
    loading = true;
    error = null;
    try {
      const [orgRes, folderRes] = await Promise.all([organizationsApi.listAll(), rulesApi.folders()]);
      orgs = orgRes.organizations;
      rulesets = folderRes;
      const nextGrants: Record<number, Set<string>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          const res = await organizationsApi.getRulesetGrants(org.id);
          nextGrants[org.id] = new SvelteSet(res.ruleset_ids);
        }),
      );
      grants = nextGrants;
      dirty.clear();
      selectedRulesetIds.clear();
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

  // Active columns to display based on org filter
  let displayOrgs = $derived(
    selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter),
  );

  // Filtered rulesets
  let filteredRulesets = $derived(
    rulesets.filter((r) => {
      const q = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !q ||
        r.display_name.toLowerCase().includes(q) ||
        r.ruleset_id.toLowerCase().includes(q);

      if (!matchesSearch) return false;

      if (grantStatusFilter === "all") return true;

      // When checking granted/ungranted:
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
      const valA = (sortField === "name" ? a.display_name : a.ruleset_id).toLowerCase();
      const valB = (sortField === "name" ? b.display_name : b.ruleset_id).toLowerCase();
      return valA < valB ? -dir : valA > valB ? dir : 0;
    });
  });

  // Paginated rulesets
  let paginatedRulesets = $derived(
    sortedRulesets.slice((pageIndex - 1) * pageSize, pageIndex * pageSize),
  );

  function handleSort(col: "name" | "id") {
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
    const orgGrants = grants[orgId];
    if (!orgGrants) return;
    if (orgGrants.has(rulesetId)) orgGrants.delete(rulesetId);
    else orgGrants.add(rulesetId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
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
    if (dirty.size === 0) return;
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

  // Bulk actions
  function handleBulkGrant() {
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
</script>

<div class="space-y-6">
  <PageHeader
    category="Administration"
    title="Ruleset Access"
    subtitle="Which rulesets each organization may use. A project can only bind what its owning organization is granted here."
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

  <!-- Controls Bar: Search, Filters, Reset -->
  <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
    <div class="flex flex-1 flex-wrap items-center gap-3">
      <!-- Search -->
      <div class="relative min-w-[16rem] flex-1 max-w-md">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Search ruleset by name or ID…"
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
          <option value="granted">Granted Only</option>
          <option value="ungranted">Ungranted Only</option>
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

    <!-- Selection summary -->
    {#if selectedRulesetIds.size > 0}
      <div class="flex items-center gap-2 text-xs text-violet-300">
        <span class="font-semibold">{selectedRulesetIds.size}</span> ruleset(s) selected
        <button
          type="button"
          onclick={() => selectedRulesetIds.clear()}
          class="text-micro underline text-slate-400 hover:text-slate-200 ml-1"
        >
          Clear
        </button>
      </div>
    {/if}
  </div>

  {#if loading}
    <LoadingState message="Loading organizations and ruleset catalog…" />
  {:else if error}
    <EmptyState title="Could not load ruleset access" description={error} icon={ShieldCheck} />
  {:else if orgs.length === 0 || rulesets.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Ruleset access requires at least one organization and one active rule folder."
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

              <!-- Organization Columns -->
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
            {#each paginatedRulesets as ruleset (ruleset.ruleset_id)}
              {@const isRowSelected = selectedRulesetIds.has(ruleset.ruleset_id)}
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

                <!-- Grant Toggle per Org -->
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
