<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    Boxes,
    ScanEye,
    CheckCircle2,
    XCircle,
    Star,
    Trash2,
    UploadCloud,
    Search,
    Download,
    RotateCw,
    FolderGit2,
    GitBranch,
    ExternalLink,
    Box,
    Loader2,
    Database,
    Plus,
    RefreshCw,
    Pencil,
  } from "lucide-svelte";
  import { modelsApi, githubReposApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import type { Model, GitHubRepo, GitHubRepoStructure } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import IsoGovernanceBadges from "../lib/components/IsoGovernanceBadges.svelte";
  import UploadModelsModal from "../lib/components/UploadModelsModal.svelte";
  import EditModelModal from "../lib/components/EditModelModal.svelte";
  import GitHubRepoManagerModal from "../lib/components/GitHubRepoManagerModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import { createTableState } from "../lib/tableState.svelte";

  interface Props {
    initialProjectId: number | null;
    onSelectProjectForViewer: (projectId: number) => void;
  }

  let { initialProjectId, onSelectProjectForViewer }: Props = $props();

  let files: Model[] = $state([]);
  let isLoading = $state(true);
  let loadError = $state("");
  let isUploadOpen = $state(false);
  let fileToDelete: Model | null = $state(null);
  let isDeleteModalOpen = $state(false);
  let isBulkDeleteModalOpen = $state(false);
  let pendingActionId: number | null = $state(null);
  let refreshingId: number | null = $state(null);
  let isEditOpen = $state(false);
  let fileToEdit: Model | null = $state(null);

  // Storage Source selector state — lets a user attach models straight from
  // a connected GitHub repository instead of uploading them by hand.
  let selectedSource = $state("supabase"); // 'supabase' or 'repo:<id>'
  let repos: GitHubRepo[] = $state([]);
  let isRepoLoading = $state(false);
  let activeRepoStructure: GitHubRepoStructure | null = $state(null);
  let repoCategoryFilter = $state("all");
  let selectedRepoPaths: Set<string> = $state(new Set());
  let primaryRepoPath: string | null = $state(null);
  let isAttaching = $state(false);
  let isRepoManagerOpen = $state(false);

  // App.svelte can briefly resolve targetProjectId to a stale value (e.g. from
  // localStorage) before its URL-sync effect corrects it, firing this
  // component's effect twice in quick succession for two different project
  // ids. Network responses are not guaranteed to arrive in request order, so
  // a request token makes a slower, stale response a no-op instead of letting
  // it clobber a newer one that already resolved.
  let loadToken = 0;

  async function loadFiles(projectId: number) {
    const token = ++loadToken;
    isLoading = true;
    loadError = "";
    try {
      const result = await modelsApi.list(projectId);
      if (token !== loadToken) return;
      files = result;
    } catch (err: any) {
      if (token !== loadToken) return;
      loadError = err?.message || "Could not load this project's models.";
      files = [];
    } finally {
      if (token === loadToken) isLoading = false;
    }
  }

  async function loadRepos() {
    try {
      repos = await githubReposApi.list();
    } catch (err: any) {
      loadError = err.message || "Failed to load connected GitHub repositories.";
    }
  }

  async function loadSelectedRepoStructure(repoId: number, force = false) {
    isRepoLoading = true;
    loadError = "";
    try {
      activeRepoStructure = await githubReposApi.getStructure(repoId, force);
    } catch (err: any) {
      activeRepoStructure = null;
      loadError = err.message || "Failed to read the repository structure.";
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
    table.search = "";
    if (selectedSource.startsWith("repo:")) {
      const repoId = parseInt(selectedSource.split(":")[1], 10);
      await loadSelectedRepoStructure(repoId);
    } else {
      activeRepoStructure = null;
    }
  }

  // App.svelte's targetProjectId can bounce back to a previously-seen id
  // while the active organization is still settling (see the
  // profile-readiness comment on App.svelte's prefetch effect); without this
  // guard each bounce re-fires this effect and piles another modelsApi.list
  // request on top of ones already in flight. Scoped to this effect alone --
  // the explicit loadFiles(initialProjectId) calls elsewhere (after
  // set-primary, delete, repo attach) must still re-fetch the same id.
  let lastEffectProjectId: number | null = null;
  $effect(() => {
    if (initialProjectId && initialProjectId !== lastEffectProjectId) {
      lastEffectProjectId = initialProjectId;
      loadFiles(initialProjectId);
    }
  });

  onMount(() => {
    loadRepos();
  });

  onDestroy(() => {
    loadToken++;
  });

  // Search, sort, paginate and select — for the attached-models table.
  const table = $state(
    createTableState<Model, number | string>({
      rows: () => files,
      getId: (f) => f.id ?? f.file_path,
      searchFields: (f) => [f.file_name, f.role, f.ifc_schema, f.authoring_application],
      comparators: {
        is_primary: (a, b) => (b.is_primary ? 1 : 0) - (a.is_primary ? 1 : 0),
        storey_count: (a, b) => (a.storey_count ?? -1) - (b.storey_count ?? -1),
        element_count: (a, b) => (a.element_count ?? -1) - (b.element_count ?? -1),
      },
      initialSort: { field: "is_primary", asc: true },
      initialPageSize: 25,
    }),
  );

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
    if (!initialProjectId || !selectedSource.startsWith("repo:") || selectedRepoPaths.size === 0) {
      return;
    }
    const repoId = parseInt(selectedSource.split(":")[1], 10);
    const filePaths = Array.from(selectedRepoPaths);
    const primaryIndex = Math.max(0, filePaths.indexOf(primaryRepoPath || filePaths[0]));

    isAttaching = true;
    loadError = "";
    try {
      await githubReposApi.attachModelsToProject(initialProjectId, {
        repo_id: repoId,
        file_paths: filePaths,
        primary_index: primaryIndex,
      });
      toasts.success(
        `Attached ${filePaths.length} model${filePaths.length === 1 ? "" : "s"} from the repository.`,
      );
      selectedRepoPaths = new Set();
      primaryRepoPath = null;
      selectedSource = "supabase";
      activeRepoStructure = null;
      await loadFiles(initialProjectId);
    } catch (err: any) {
      loadError = err.message || "Failed to attach model(s) from GitHub repository.";
    } finally {
      isAttaching = false;
    }
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  function handleUploaded(updated: Model[]) {
    files = updated;
    isUploadOpen = false;
  }

  const DISCIPLINE_LABELS: Record<string, string> = {
    architectural: "Arch",
    structural: "Struct",
    mep: "MEP",
    other: "Other",
  };

  /** Top disciplines by element count, e.g. "MEP 120 · Arch 40 · +1 more". */
  function disciplineSummaryLabel(file: Model): string {
    const entries = Object.entries(file.discipline_summary ?? {}).filter(([, n]) => n > 0);
    if (entries.length === 0) return "—";
    entries.sort((a, b) => b[1] - a[1]);
    const shown = entries
      .slice(0, 2)
      .map(([key, n]) => `${DISCIPLINE_LABELS[key] ?? key} ${n}`)
      .join(" · ");
    return entries.length > 2 ? `${shown} · +${entries.length - 2} more` : shown;
  }

  async function handleSetPrimary(file: Model) {
    if (!initialProjectId || file.id == null || file.is_primary) return;
    pendingActionId = file.id;
    try {
      await modelsApi.setPrimary(initialProjectId, file.id);
      files = await modelsApi.list(initialProjectId);
    } catch (err) {
      toasts.fromError(err, "Could not set this model as primary.");
    } finally {
      pendingActionId = null;
    }
  }

  async function handleRefreshMetadata(file: Model) {
    if (!initialProjectId || file.id == null) return;
    refreshingId = file.id;
    try {
      const updated = await modelsApi.refreshMetadata(initialProjectId, file.id);
      files = files.map((f) => (f.id === updated.id ? updated : f));
      toasts.success(`Refreshed metadata for "${file.file_name}".`);
    } catch (err) {
      toasts.fromError(err, "Could not refresh this model's metadata.");
    } finally {
      refreshingId = null;
    }
  }

  function openEditModal(file: Model) {
    fileToEdit = file;
    isEditOpen = true;
  }

  function handleModelSaved(updated: Model) {
    files = files.map((f) => (f.id === updated.id ? updated : f));
    isEditOpen = false;
    toasts.success(`Saved changes to "${updated.file_name}".`);
  }

  function promptDelete(file: Model) {
    fileToDelete = file;
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!initialProjectId || fileToDelete?.id == null) return;
    try {
      await modelsApi.delete(initialProjectId, fileToDelete.id);
      files = files.filter((f) => f.id !== fileToDelete!.id);
      table.selectedIds.delete(fileToDelete.id);
      toasts.success(`Removed "${fileToDelete.file_name}".`);
    } catch (err) {
      toasts.fromError(err, "Could not delete this model.");
    } finally {
      fileToDelete = null;
    }
  }

  async function confirmBulkDelete() {
    if (!initialProjectId || !table.selectedCount) return;
    const ids = table.selectedIdList.filter((id): id is number => typeof id === "number");
    const results = await Promise.allSettled(
      ids.map((id) => modelsApi.delete(initialProjectId!, id)),
    );
    const failed = results.filter((r) => r.status === "rejected").length;
    files = files.filter((f) => f.id == null || !ids.includes(f.id));
    table.clearSelection();
    isBulkDeleteModalOpen = false;
    if (failed > 0) {
      toasts.error(`${failed} model(s) could not be deleted.`);
    } else {
      toasts.success(`Deleted ${ids.length} model(s).`);
    }
  }
</script>

<div class="mx-auto space-y-6">
  <PageHeader
    category="Project"
    title="Models"
    subtitle="IFC models attached to this project — the primary model and any supporting context files."
    icon={Boxes}
  >
    {#snippet actions()}
      <div class="flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          onclick={() => (isUploadOpen = true)}
          disabled={!initialProjectId}
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <UploadCloud class="h-3.5 w-3.5" />
          <span>Attach Model</span>
        </button>

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
            class="max-w-[240px] truncate rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs font-semibold text-slate-50 focus:border-blue-500 focus:outline-hidden"
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
              onclick={() => initialProjectId && loadFiles(initialProjectId)}
              class="rounded-xl border border-slate-800 bg-slate-950 p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
              title="Refresh attached models"
            >
              <RotateCw class="h-3.5 w-3.5 {isLoading ? 'animate-spin text-blue-400' : ''}" />
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

  {#if loadError}
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
      {loadError}
    </div>
  {/if}

  <!-- VIEW 1: ATTACHED MODELS (this project's registry) -->
  {#if selectedSource === "supabase"}
    <div
      class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 md:flex-row"
    >
      <div class="relative w-full flex-1">
        <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          bind:value={table.search}
          placeholder="Filter models by filename or role..."
          class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-hidden"
        />
      </div>
    </div>

    <BulkActionBar
      selectedCount={table.selectedCount}
      itemLabel="model"
      onClearSelection={() => table.clearSelection()}
      onBulkDelete={() => (isBulkDeleteModalOpen = true)}
    />

    <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
      {#if isLoading}
        <LoadingState message="Loading models…" />
      {:else if table.totalItems === 0}
        <div class="p-6">
          <EmptyState
            icon={Boxes}
            title={files.length === 0 ? "No models attached" : "No models match your search"}
            description={files.length === 0
              ? "Attach an IFC model to make this project ready for the 3D Viewer and Compliance Audit."
              : "Adjust your search to see attached models."}
            actionLabel={files.length === 0 ? "Attach Model" : "Reset search"}
            onAction={() => (files.length === 0 ? (isUploadOpen = true) : table.reset())}
          />
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead class="border-b border-slate-800">
              <tr>
                <th class="w-10 px-4 py-3">
                  <TableCheckbox
                    checked={table.allFilteredSelected}
                    indeterminate={table.someFilteredSelected}
                    onchange={() => table.toggleSelectAll()}
                    title="Select or deselect all visible models"
                  />
                </th>
                <SortHeader
                  column="file_name"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}>File</SortHeader
                >
                <SortHeader
                  column="role"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}>Role</SortHeader
                >
                <th class="px-4 py-3 text-caption font-semibold uppercase tracking-wider text-slate-400"
                  >ISO 19650</th
                >
                <SortHeader
                  column="ifc_schema"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}>Schema</SortHeader
                >
                <SortHeader
                  column="storey_count"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}>Storeys</SortHeader
                >
                <SortHeader
                  column="element_count"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}>Elements</SortHeader
                >
                <th class="px-4 py-3 text-caption font-semibold uppercase tracking-wider text-slate-400"
                  >Discipline</th
                >
                <SortHeader
                  column="uploaded_at"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}>Uploaded</SortHeader
                >
                <th
                  class="px-4 py-3 text-right text-caption font-semibold uppercase tracking-wider text-slate-400"
                  >Actions</th
                >
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#each table.paginated as file (file.id ?? file.file_path)}
                <tr
                  class="transition-colors hover:bg-slate-900/60 {table.isSelected(
                    file.id ?? file.file_path,
                  )
                    ? 'bg-blue-950/20'
                    : ''}"
                >
                  <td class="w-10 px-4 py-3">
                    <TableCheckbox
                      checked={table.isSelected(file.id ?? file.file_path)}
                      onchange={() => table.toggleSelect(file.id ?? file.file_path)}
                      ariaLabel={`Select model ${file.file_name}`}
                    />
                  </td>
                  <td class="max-w-xs truncate px-4 py-3">
                    <div class="truncate font-semibold text-slate-50" title={file.file_name}>
                      {file.file_name}
                    </div>
                    {#if file.authoring_application}
                      <div class="truncate text-micro text-slate-500" title={file.authoring_application}>
                        {file.authoring_application}
                      </div>
                    {/if}
                  </td>
                  <td class="px-4 py-3">
                    {#if file.is_primary}
                      <span
                        class="inline-flex items-center gap-1.5 rounded-md border border-emerald-800/60 bg-emerald-950/40 px-2 py-0.5 text-micro font-semibold uppercase tracking-wider text-emerald-400"
                      >
                        <CheckCircle2 class="h-3 w-3" />
                        Primary
                      </span>
                    {:else}
                      <span
                        class="inline-block rounded-md border border-slate-700/60 bg-slate-800 px-2 py-0.5 text-micro font-semibold uppercase tracking-wider text-slate-400"
                      >
                        {file.role || "context"}
                      </span>
                    {/if}
                  </td>
                  <td class="px-4 py-3">
                    <IsoGovernanceBadges
                      suitability={file.suitability_code}
                      revision={file.revision_code}
                      cdeState={file.cde_state}
                    />
                  </td>
                  <td class="px-4 py-3 text-slate-400">
                    {file.ifc_schema || "—"}
                  </td>
                  <td class="px-4 py-3 text-right text-slate-400">
                    {file.storey_count ?? "—"}
                  </td>
                  <td class="px-4 py-3 text-right text-slate-400">
                    {file.element_count ?? "—"}
                  </td>
                  <td class="px-4 py-3 text-slate-400" title={JSON.stringify(file.discipline_summary ?? {})}>
                    {disciplineSummaryLabel(file)}
                  </td>
                  <td class="px-4 py-3 text-slate-400">
                    {file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : "—"}
                  </td>
                  <td class="px-4 py-3 text-right">
                    <div class="flex items-center justify-end gap-1.5">
                      <button
                        type="button"
                        onclick={() => initialProjectId && onSelectProjectForViewer(initialProjectId)}
                        class="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                        title="Open in 3D Viewer"
                      >
                        <ScanEye class="h-3.5 w-3.5" />
                      </button>

                      {#if file.id != null}
                        <button
                          type="button"
                          onclick={() => handleSetPrimary(file)}
                          disabled={file.is_primary || pendingActionId === file.id}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-amber-950/30 hover:text-amber-400 disabled:cursor-not-allowed disabled:opacity-40"
                          title={file.is_primary ? "Already primary" : "Set as primary model"}
                        >
                          <Star class="h-3.5 w-3.5" />
                        </button>

                        <button
                          type="button"
                          onclick={() => handleRefreshMetadata(file)}
                          disabled={refreshingId === file.id}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-blue-950/30 hover:text-blue-400 disabled:cursor-not-allowed disabled:opacity-40"
                          title="Refresh IFC metadata (schema, storeys, elements, discipline)"
                        >
                          <RefreshCw
                            class="h-3.5 w-3.5 {refreshingId === file.id ? 'animate-spin' : ''}"
                          />
                        </button>

                        <button
                          type="button"
                          onclick={() => openEditModal(file)}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-50"
                          title="Edit model (name, ISO 19650 fields, replace file)"
                        >
                          <Pencil class="h-3.5 w-3.5" />
                        </button>

                        <button
                          type="button"
                          onclick={() => promptDelete(file)}
                          class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                          title="Delete model"
                        >
                          <Trash2 class="h-3.5 w-3.5" />
                        </button>
                      {/if}
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
              class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-blue-500 focus:outline-hidden"
            />
          </div>

          {#if activeRepoStructure.categories.length > 0}
            <div class="flex w-full items-center gap-2 md:w-auto">
              <select
                bind:value={repoCategoryFilter}
                class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-blue-500 focus:outline-hidden"
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
          disabled={!initialProjectId || isAttaching}
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {#if isAttaching}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
            <span>Attaching…</span>
          {:else}
            <Boxes class="h-3.5 w-3.5" />
            <span>Attach to this project</span>
          {/if}
        </button>
      </div>
    {/if}
  {/if}
</div>

<UploadModelsModal
  isOpen={isUploadOpen}
  projectId={initialProjectId}
  onClose={() => (isUploadOpen = false)}
  onUploaded={handleUploaded}
/>

<EditModelModal
  isOpen={isEditOpen}
  projectId={initialProjectId}
  file={fileToEdit}
  onClose={() => (isEditOpen = false)}
  onSaved={handleModelSaved}
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
  title="Delete Model"
  message={`Are you sure you want to delete "${fileToDelete?.file_name || ""}"? This cannot be undone.${
    fileToDelete?.is_primary
      ? " Its role as the primary model will pass to another attached model, if one remains."
      : ""
  }`}
  confirmText="Delete Model"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => (fileToDelete = null)}
/>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title="Delete Selected Models"
  message={`Are you sure you want to delete ${table.selectedCount} model(s)? This cannot be undone.`}
  confirmText={`Delete ${table.selectedCount} Model(s)`}
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => (isBulkDeleteModalOpen = false)}
/>
