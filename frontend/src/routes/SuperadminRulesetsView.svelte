<script lang="ts">
  import { ShieldCheck, Save, CheckCircle2, XCircle, Eye, Info, Trash2 } from "lucide-svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import Select from "../lib/components/ui/Select.svelte";
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
  import { downloadText } from "../lib/utils/download";
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
  let orgFilterOptions = $derived([
    ...(isSuperadmin ? [{ value: "all", label: `All Organizations (${orgs.length})` }] : []),
    ...orgs.map((o) => ({ value: String(o.id), label: o.name })),
  ]);
  let orgPickerOptions = $derived([
    { value: "all", label: "All Organizations" },
    ...orgs.map((o) => ({ value: String(o.id), label: o.name })),
  ]);
  let sortField = $state<"name" | "id" | "category" | "count">("name");
  let sortAsc = $state(true);
  let pageIndex = $state(1);
  let pageSize = $state(10);
  const selectedRulesetIds: Set<string> = new SvelteSet();

  // Target org for bulk grant/revoke
  let bulkTargetOrgId = $state<number | "all">("all");

  // Inspection modal
  let inspectingRuleset = $state<RuleFolder | null>(null);

  // Delete confirmation
  let deletingRuleset = $state<RuleFolder | null>(null);

  async function confirmDeleteRuleset() {
    if (!deletingRuleset) return;
    const target = deletingRuleset;
    const prevRulesets = [...rulesets];
    deletingRuleset = null;

    // Optimistic removal
    rulesets = rulesets.filter((r) => r.ruleset_id !== target.ruleset_id);
    selectedRulesetIds.delete(target.ruleset_id);

    try {
      await rulesApi.deleteFolder(target.ruleset_id);
      toasts.success(`Ruleset "${target.display_name}" deleted.`);
    } catch (err) {
      rulesets = prevRulesets;
      selectedRulesetIds.add(target.ruleset_id);
      toasts.fromError(err, "Could not delete ruleset.");
    }
  }

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
          org_code: o.org_code,
        }));
      }
      orgs = loadedOrgs;

      const folderRes = await rulesApi.folders();
      rulesets = folderRes;

      const nextGrants: Record<number, Set<string>> = {};
      let failedGrantOrgs = 0;
      await Promise.all(
        orgs.map(async (org) => {
          try {
            const res = await organizationsApi.getRulesetGrants(org.id);
            nextGrants[org.id] = new SvelteSet(res.ruleset_ids);
          } catch {
            nextGrants[org.id] = new SvelteSet();
            failedGrantOrgs += 1;
          }
        }),
      );
      grants = nextGrants;
      if (failedGrantOrgs > 0) {
        toasts.warning(
          `Could not load ruleset grants for ${failedGrantOrgs} organization(s) -- they show as ungranted below but may not be.`,
        );
      }
      dirty.clear();
      selectedRulesetIds.clear();

      if (
        authState.activeOrganizationId &&
        orgs.some((o) => o.id === authState.activeOrganizationId)
      ) {
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
      selectedOrgFilter !==
        (isSuperadmin ? "all" : authState.activeOrganizationId || (orgs[0]?.id ?? "all")) ||
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

      const checkOrgs =
        selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter);
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
    const csvContent = ["Ruleset ID,Display Name,Category,Rule Count,Description"]
      .concat(
        selectedList.map(
          (r) =>
            `"${r.ruleset_id}","${r.display_name}","${r.category || ""}","${r.rules?.length || r.count || 0}","${(r.description || "").replace(/"/g, '""')}"`,
        ),
      )
      .join("\n");
    const filename = `rulesets-export-${new Date().toISOString().slice(0, 10)}.csv`;
    downloadText(csvContent, filename, "text/csv;charset=utf-8;");
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
          class="bg-accent hover:bg-accent-hover inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-semibold text-white shadow-xs transition-all disabled:opacity-50"
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
        <Select
          bind:value={
            () => String(selectedOrgFilter),
            (v) => (selectedOrgFilter = v === "all" ? "all" : Number(v))
          }
          ariaLabel="Filter by Organization"
          options={orgFilterOptions}
          class="w-auto min-w-48"
        />
      {/if}

      <!-- Category Filter -->
      <Select
        bind:value={categoryFilter}
        ariaLabel="Filter by Category"
        options={[
          { value: "all", label: "All Categories" },
          ...categories.map((cat) => ({ value: cat, label: cat })),
        ]}
        class="w-auto min-w-40"
      />

      <!-- Grant Status Filter -->
      <Select
        bind:value={grantStatusFilter}
        ariaLabel="Filter by Grant Status"
        options={[
          { value: "all", label: "All Statuses" },
          { value: "granted", label: "Granted Only" },
          { value: "ungranted", label: "Ungranted Only" },
        ]}
        class="w-auto min-w-40"
      />
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
    <div
      class="border-border-default bg-surface-card/40 overflow-hidden rounded-2xl border shadow-xl"
    >
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs">
          <thead>
            <tr class="border-border-default bg-surface-canvas/80 border-b">
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
                customClass="min-w-56 px-4 py-3"
              >
                Ruleset Name
              </SortHeader>

              <!-- Sortable Ruleset ID -->
              <SortHeader
                column="id"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("id")}
                customClass="min-w-48 px-4 py-3"
              >
                Ruleset ID
              </SortHeader>

              <!-- Category -->
              <SortHeader
                column="category"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("category")}
                customClass="min-w-36 px-4 py-3"
              >
                Category
              </SortHeader>

              <!-- Rules Count -->
              <SortHeader
                column="count"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("count")}
                customClass="min-w-28 px-4 py-3 text-center"
                align="center"
              >
                Rules
              </SortHeader>

              <!-- Organization Grant Columns (Superadmin Multi-Org View) -->
              {#if isSuperadmin && displayOrgs.length > 1}
                {#each displayOrgs as org (org.id)}
                  <th class="min-w-44 px-4 py-3 text-center">
                    <div class="text-fg-primary truncate font-semibold" title={org.name}>
                      {org.name}
                    </div>
                    <button
                      type="button"
                      disabled={!dirty.has(org.id) || savingOrgId === org.id}
                      onclick={() => saveOrg(org.id)}
                      class="border-border-interactive bg-surface-overlay text-micro text-fg-secondary hover:bg-surface-hover mt-1 inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <Save class="h-3 w-3" />
                      <span
                        >{savingOrgId === org.id
                          ? "Saving…"
                          : dirty.has(org.id)
                            ? "Save"
                            : "Saved"}</span
                      >
                    </button>
                  </th>
                {/each}
              {:else}
                <!-- Single Org Access Status Column (Org Owner View or Single-Filtered Superadmin) -->
                {@const targetOrg = displayOrgs[0] || orgs[0]}
                <th class="min-w-48 px-4 py-3 text-center">
                  <div class="text-fg-primary font-semibold">
                    {targetOrg?.name || "Organization"} Access
                  </div>
                  {#if isSuperadmin && targetOrg && dirty.has(targetOrg.id)}
                    <button
                      type="button"
                      disabled={savingOrgId === targetOrg.id}
                      onclick={() => saveOrg(targetOrg.id)}
                      class="border-accent/40 bg-accent/20 text-micro text-accent hover:bg-accent/30 mt-1 inline-flex items-center gap-1 rounded-lg border px-2.5 py-0.5 font-semibold transition-colors"
                    >
                      <Save class="h-3 w-3" />
                      <span>{savingOrgId === targetOrg.id ? "Saving…" : "Save Changes"}</span>
                    </button>
                  {/if}
                </th>
              {/if}

              <!-- Actions Column -->
              <th class="w-20 px-4 py-3 text-center">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-border-subtle divide-y">
            {#each paginatedRulesets as ruleset (ruleset.ruleset_id)}
              {@const isRowSelected = selectedRulesetIds.has(ruleset.ruleset_id)}
              {@const singleOrg = displayOrgs[0] || orgs[0]}
              {@const isSingleOrgGranted = singleOrg
                ? (grants[singleOrg.id]?.has(ruleset.ruleset_id) ?? false)
                : false}
              <tr
                class="hover:bg-surface-hover transition-colors {isRowSelected
                  ? 'bg-surface-selected'
                  : ''}"
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
                <td class="text-fg-secondary px-4 py-3 font-medium">
                  <div class="text-fg-primary truncate font-semibold" title={ruleset.display_name}>
                    {ruleset.display_name}
                  </div>
                  {#if ruleset.description}
                    <div class="text-micro text-fg-muted truncate" title={ruleset.description}>
                      {ruleset.description}
                    </div>
                  {/if}
                </td>

                <!-- Ruleset ID -->
                <td class="text-micro text-fg-muted px-4 py-3 font-mono">
                  <span class="bg-surface-overlay text-fg-secondary rounded px-1.5 py-0.5">
                    {ruleset.ruleset_id}
                  </span>
                </td>

                <!-- Category -->
                <td class="px-4 py-3">
                  <span
                    class="border-border-default bg-surface-card/60 text-micro text-fg-secondary rounded-lg border px-2 py-0.5 font-medium"
                  >
                    {ruleset.category || "General"}
                  </span>
                </td>

                <!-- Rule Count -->
                <td class="text-micro text-fg-secondary px-4 py-3 text-center font-mono">
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
                          : 'border-border-interactive bg-surface-overlay text-fg-muted hover:border-border-interactive hover:text-fg-primary'}"
                        title={isGranted ? `Revoke from ${org.name}` : `Grant to ${org.name}`}
                      >
                        {#if isGranted}
                          <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                          <span>Granted</span>
                        {:else}
                          <XCircle
                            class="text-fg-muted group-hover:text-fg-secondary h-3.5 w-3.5"
                          />
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
                          : 'border-border-interactive bg-surface-overlay text-fg-muted hover:border-border-interactive hover:text-fg-primary'}"
                        title={isSingleOrgGranted ? `Click to revoke` : `Click to grant`}
                      >
                        {#if isSingleOrgGranted}
                          <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                          <span>Granted</span>
                        {:else}
                          <XCircle
                            class="text-fg-muted group-hover:text-fg-secondary h-3.5 w-3.5"
                          />
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
                          class="border-border-interactive bg-surface-overlay text-fg-muted inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium"
                        >
                          <Info class="text-fg-muted h-3.5 w-3.5" />
                          <span>Catalog Standard</span>
                        </span>
                      {/if}
                    {/if}
                  </td>
                {/if}

                <!-- Row Actions -->
                <td class="px-4 py-3 text-center">
                  <div class="flex items-center justify-center gap-1">
                    <button
                      type="button"
                      onclick={() => (inspectingRuleset = ruleset)}
                      class="text-fg-muted hover:bg-surface-hover hover:text-fg-primary rounded-lg p-1.5 transition-colors"
                      title="Inspect ruleset rules and metadata"
                    >
                      <Eye class="h-4 w-4" />
                    </button>
                    {#if isSuperadmin}
                      <button
                        type="button"
                        onclick={() => (deletingRuleset = ruleset)}
                        class="text-fg-muted rounded-lg p-1.5 transition-colors hover:bg-rose-950/60 hover:text-rose-400"
                        title="Delete ruleset"
                      >
                        <Trash2 class="h-4 w-4" />
                      </button>
                    {/if}
                  </div>
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
        <Select
          bind:value={
            () => String(bulkTargetOrgId),
            (v) => (bulkTargetOrgId = v === "all" ? "all" : Number(v))
          }
          ariaLabel="Target Organization for Bulk Action"
          options={orgPickerOptions}
          class="w-auto min-w-44"
          triggerClass="h-8"
        />
        <button
          type="button"
          onclick={handleBulkGrant}
          class="rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500"
        >
          Grant Access
        </button>
        <button
          type="button"
          onclick={handleBulkRevoke}
          class="rounded-lg bg-rose-600 px-2.5 py-1 text-xs font-semibold text-white shadow-sm hover:bg-rose-500"
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

  <!-- Delete Confirmation -->
  <ConfirmModal
    isOpen={deletingRuleset !== null}
    title="Delete ruleset?"
    message={deletingRuleset
      ? `This permanently deletes "${deletingRuleset.display_name}" and every rule in it, for every organization. This cannot be undone.`
      : ""}
    confirmText="Delete Ruleset"
    danger={true}
    optimistic={true}
    onConfirm={confirmDeleteRuleset}
    onCancel={() => (deletingRuleset = null)}
  />
</div>
