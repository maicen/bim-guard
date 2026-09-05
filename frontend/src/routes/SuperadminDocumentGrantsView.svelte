<script lang="ts">
  import {
    ShieldCheck,
    Save,
    CheckCircle2,
    XCircle,
    Building2,
    Filter,
    FileText,
    Eye,
    Tag,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";
  import Modal from "../lib/components/Modal.svelte";
  import { organizationsApi, documentsApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { DocumentItem, OrganizationSummary } from "../lib/types";

  let isSuperadmin = $derived(authState.isSuperadmin);

  let orgs = $state.raw<OrganizationSummary[]>([]);
  let documents = $state.raw<DocumentItem[]>([]);
  let grants = $state.raw<Record<number, Set<number>>>({});
  const dirty: Set<number> = new SvelteSet();
  let loading = $state(true);
  let error = $state<string | null>(null);
  let savingOrgId = $state<number | null>(null);
  let isSavingAll = $state(false);

  // Table state: search, filter, sort, pagination, selection
  let searchQuery = $state("");
  let selectedOrgFilter = $state<number | "all">("all");
  let docTypeFilter = $state<string>("all");
  let grantStatusFilter = $state<"all" | "granted" | "ungranted">("all");
  let sortField = $state<"filename" | "type" | "id">("filename");
  let sortAsc = $state(true);
  let pageIndex = $state(1);
  let pageSize = $state(10);
  const selectedDocIds: Set<number> = new SvelteSet();

  let bulkTargetOrgId = $state<number | "all">("all");

  // Document preview modal
  let previewDocId = $state<number | null>(null);

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

      const docs = await documentsApi.list();
      documents = docs;

      const nextGrants: Record<number, Set<number>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          try {
            const res = await organizationsApi.getDocumentGrants(org.id);
            nextGrants[org.id] = new SvelteSet(res.document_ids);
          } catch {
            nextGrants[org.id] = new SvelteSet();
          }
        }),
      );
      grants = nextGrants;
      dirty.clear();
      selectedDocIds.clear();

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

  let displayOrgs = $derived(
    selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter),
  );

  let docTypes = $derived(
    Array.from(new Set(documents.map((d) => d.doc_type || "Specification"))).filter(Boolean),
  );

  let hasActiveFilters = $derived(
    searchQuery.trim() !== "" ||
      selectedOrgFilter !== (isSuperadmin ? "all" : (authState.activeOrganizationId || (orgs[0]?.id ?? "all"))) ||
      docTypeFilter !== "all" ||
      grantStatusFilter !== "all",
  );

  let filteredDocs = $derived(
    documents.filter((d) => {
      const q = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !q ||
        d.filename.toLowerCase().includes(q) ||
        (d.project_code && d.project_code.toLowerCase().includes(q)) ||
        (d.originator && d.originator.toLowerCase().includes(q));

      if (!matchesSearch) return false;

      if (docTypeFilter !== "all" && (d.doc_type || "Specification") !== docTypeFilter) {
        return false;
      }

      if (grantStatusFilter === "all") return true;

      const checkOrgs = selectedOrgFilter === "all" ? orgs : orgs.filter((o) => o.id === selectedOrgFilter);
      const isGrantedAny = checkOrgs.some((o) => grants[o.id]?.has(d.id));

      if (grantStatusFilter === "granted") return isGrantedAny;
      if (grantStatusFilter === "ungranted") return !isGrantedAny;

      return true;
    }),
  );

  let sortedDocs = $derived.by(() => {
    const dir = sortAsc ? 1 : -1;
    return [...filteredDocs].sort((a, b) => {
      if (sortField === "filename") {
        return a.filename.localeCompare(b.filename) * dir;
      }
      if (sortField === "type") {
        return (a.doc_type || "").localeCompare(b.doc_type || "") * dir;
      }
      return (a.id - b.id) * dir;
    });
  });

  let paginatedDocs = $derived(
    sortedDocs.slice((pageIndex - 1) * pageSize, pageIndex * pageSize),
  );

  function handleSort(col: "filename" | "type" | "id") {
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
    docTypeFilter = "all";
    grantStatusFilter = "all";
    pageIndex = 1;
  }

  function toggleSelectRow(docId: number) {
    if (selectedDocIds.has(docId)) {
      selectedDocIds.delete(docId);
    } else {
      selectedDocIds.add(docId);
    }
  }

  function toggleSelectAll() {
    const pageIds = paginatedDocs.map((d) => d.id);
    const allSelected = pageIds.every((id) => selectedDocIds.has(id));
    for (const id of pageIds) {
      if (allSelected) selectedDocIds.delete(id);
      else selectedDocIds.add(id);
    }
  }

  let allOnPageSelected = $derived(
    paginatedDocs.length > 0 && paginatedDocs.every((d) => selectedDocIds.has(d.id)),
  );
  let someOnPageSelected = $derived(
    paginatedDocs.some((d) => selectedDocIds.has(d.id)) && !allOnPageSelected,
  );

  function toggleGrant(orgId: number, docId: number) {
    if (!isSuperadmin) return;
    const orgGrants = grants[orgId];
    if (!orgGrants) return;
    if (orgGrants.has(docId)) orgGrants.delete(docId);
    else orgGrants.add(docId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
    if (!isSuperadmin) return;
    savingOrgId = orgId;
    try {
      await organizationsApi.setDocumentGrants(orgId, Array.from(grants[orgId] ?? []));
      dirty.delete(orgId);
      toasts.success("Document access updated.");
    } catch (err) {
      toasts.fromError(err, "Could not save document access.");
    } finally {
      savingOrgId = null;
    }
  }

  async function saveAllDirty() {
    if (!isSuperadmin || dirty.size === 0) return;
    isSavingAll = true;
    try {
      for (const orgId of Array.from(dirty)) {
        await organizationsApi.setDocumentGrants(orgId, Array.from(grants[orgId] ?? []));
        dirty.delete(orgId);
      }
      toasts.success("All organization document grants saved.");
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
      for (const docId of selectedDocIds) {
        orgSet.add(docId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Granted ${selectedDocIds.size} document(s). Click Save to persist.`);
  }

  function handleBulkRevoke() {
    if (!isSuperadmin) return;
    const targetOrgIds =
      bulkTargetOrgId === "all" ? orgs.map((o) => o.id) : [Number(bulkTargetOrgId)];
    for (const orgId of targetOrgIds) {
      const orgSet = grants[orgId];
      if (!orgSet) continue;
      for (const docId of selectedDocIds) {
        orgSet.delete(docId);
      }
      dirty.add(orgId);
    }
    toasts.success(`Revoked ${selectedDocIds.size} document(s). Click Save to persist.`);
  }

  function exportSelectedDocs() {
    const selectedList = documents.filter((d) => selectedDocIds.has(d.id));
    const csvContent =
      "data:text/csv;charset=utf-8," +
      ["Document ID,Filename,Doc Type,Project Code,Originator,CDE State"]
        .concat(
          selectedList.map(
            (d) =>
              `"${d.id}","${d.filename}","${d.doc_type || ""}","${d.project_code || ""}","${d.originator || ""}","${d.cde_state || ""}"`,
          ),
        )
        .join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `documents-access-export-${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toasts.success(`Exported ${selectedList.length} document(s) to CSV.`);
  }
</script>

<div class="space-y-6">
  <PageHeader
    category={isSuperadmin ? "Platform Governance" : "Organization Governance"}
    title="Document Access"
    subtitle={isSuperadmin
      ? "Which specification documents each organization is permitted to bind to its projects."
      : "Specification documents and building standards licensed for your organization's projects."}
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
    searchPlaceholder="Search documents by filename, code, originator…"
    selectedCount={selectedDocIds.size}
    selectedLabel="document"
    onClearSelection={() => selectedDocIds.clear()}
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

      <!-- Doc Type Filter -->
      <div class="relative">
        <select
          bind:value={docTypeFilter}
          aria-label="Filter by Document Type"
          class="cursor-pointer appearance-none rounded-xl border border-slate-700 bg-slate-950 py-2 pl-3 pr-8 text-xs font-medium text-slate-300 focus:border-violet-500 focus:outline-none"
        >
          <option value="all">All Types</option>
          {#each docTypes as dt}
            <option value={dt}>{dt}</option>
          {/each}
        </select>
        <FileText class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
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
    <LoadingState message="Loading organizations and documents…" />
  {:else if error}
    <EmptyState title="Could not load document access" description={error} icon={ShieldCheck} />
  {:else if orgs.length === 0 || documents.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Document access requires at least one organization and one document in the library."
      icon={ShieldCheck}
    />
  {:else if filteredDocs.length === 0}
    <EmptyState
      title="No matching documents"
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
                  ariaLabel="Select all documents on page"
                />
              </th>
              <SortHeader
                column="filename"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("filename")}
                customClass="min-w-[16rem] px-4 py-3"
              >
                Document Name
              </SortHeader>
              <SortHeader
                column="type"
                {sortField}
                {sortAsc}
                onSort={() => handleSort("type")}
                customClass="min-w-[10rem] px-4 py-3"
              >
                Type
              </SortHeader>

              <!-- Superadmin Multi-Org View -->
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
                <!-- Org Owner View: Single Org Status & Preview -->
                {@const singleOrg = displayOrgs[0] || orgs[0]}
                <th class="min-w-[12rem] px-4 py-3 text-center">
                  <div class="font-semibold text-slate-100">
                    {singleOrg?.name || "Organization"} Access
                  </div>
                  {#if isSuperadmin && singleOrg && dirty.has(singleOrg.id)}
                    <button
                      type="button"
                      disabled={savingOrgId === singleOrg.id}
                      onclick={() => saveOrg(singleOrg.id)}
                      class="mt-1 inline-flex items-center gap-1 rounded-lg border border-violet-500/40 bg-violet-600/30 px-2.5 py-0.5 text-micro font-semibold text-violet-200 transition-colors hover:bg-violet-600/50"
                    >
                      <Save class="h-3 w-3" />
                      <span>{savingOrgId === singleOrg.id ? "Saving…" : "Save Changes"}</span>
                    </button>
                  {/if}
                </th>
              {/if}
              <th class="w-16 px-4 py-3 text-center">Preview</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each paginatedDocs as doc (doc.id)}
              {@const isRowSelected = selectedDocIds.has(doc.id)}
              {@const singleOrg = displayOrgs[0] || orgs[0]}
              {@const isSingleOrgGranted = singleOrg ? (grants[singleOrg.id]?.has(doc.id) ?? false) : false}
              <tr
                class="transition-colors hover:bg-slate-800/40 {isRowSelected ? 'bg-violet-950/20' : ''}"
              >
                <td class="px-4 py-3 text-center">
                  <TableCheckbox
                    checked={isRowSelected}
                    onchange={() => toggleSelectRow(doc.id)}
                    ariaLabel={`Select ${doc.filename}`}
                  />
                </td>
                <td class="px-4 py-3 font-medium text-slate-200">
                  <div class="truncate font-semibold text-slate-100" title={doc.filename}>
                    {doc.filename}
                  </div>
                  <div class="text-micro text-slate-500 font-mono flex items-center gap-1.5 mt-0.5">
                    <span>#{doc.id}</span>
                    {#if doc.project_code}<span>&middot; {doc.project_code}</span>{/if}
                    {#if doc.cde_state}
                      <span class="rounded bg-slate-900 border border-slate-800 px-1 py-0.2 text-slate-400">
                        {doc.cde_state}
                      </span>
                    {/if}
                  </div>
                </td>
                <td class="px-4 py-3">
                  <span class="rounded bg-slate-800/80 px-2 py-0.5 text-micro text-slate-300 font-medium">
                    {doc.doc_type || "Specification"}
                  </span>
                </td>

                <!-- Superadmin Multi-Org Columns -->
                {#if isSuperadmin && displayOrgs.length > 1}
                  {#each displayOrgs as org (org.id)}
                    {@const isGranted = grants[org.id]?.has(doc.id) ?? false}
                    <td class="px-4 py-3 text-center">
                      <button
                        type="button"
                        onclick={() => toggleGrant(org.id, doc.id)}
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
                    </td>
                  {/each}
                {:else}
                  <!-- Org Owner View: Single Org Status -->
                  <td class="px-4 py-3 text-center">
                    {#if isSuperadmin && singleOrg}
                      <button
                        type="button"
                        onclick={() => toggleGrant(singleOrg.id, doc.id)}
                        class="group inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-xs font-semibold transition-all {isSingleOrgGranted
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                          : 'border-slate-700 bg-slate-800/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'}"
                        title={isSingleOrgGranted ? "Click to revoke" : "Click to grant"}
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
                      {#if isSingleOrgGranted}
                        <span class="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-300">
                          <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                          <span>Granted to Org</span>
                        </span>
                      {:else}
                        <span class="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-xs font-medium text-slate-400">
                          <Tag class="h-3.5 w-3.5 text-slate-500" />
                          <span>Catalog Specification</span>
                        </span>
                      {/if}
                    {/if}
                  </td>
                {/if}

                <!-- Preview / Inspect Document -->
                <td class="px-4 py-3 text-center">
                  <button
                    type="button"
                    onclick={() => (previewDocId = doc.id)}
                    class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
                    title="Preview specification document"
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
        totalItems={sortedDocs.length}
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
    selectedCount={selectedDocIds.size}
    itemLabel="document"
    onClearSelection={() => selectedDocIds.clear()}
    onBulkExport={exportSelectedDocs}
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

  <!-- Document Viewer Modal -->
  {#if previewDocId !== null}
    {@const previewDoc = documents.find((d) => d.id === previewDocId)}
    <Modal
      isOpen={previewDocId !== null}
      onClose={() => (previewDocId = null)}
      title={previewDoc?.filename || "Document Viewer"}
      icon={FileText}
      maxWidth="max-w-4xl"
    >
      <div class="h-[65vh] overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <DocumentViewer documentId={previewDocId} />
      </div>
      {#snippet footer()}
        <button
          type="button"
          onclick={() => (previewDocId = null)}
          class="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-700"
        >
          Close
        </button>
      {/snippet}
    </Modal>
  {/if}
</div>
