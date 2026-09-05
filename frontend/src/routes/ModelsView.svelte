<script lang="ts">
  import { Boxes, ScanEye, CheckCircle2, Star, Trash2, UploadCloud } from "lucide-svelte";
  import { projectsApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import type { ProjectIfcFile } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import IsoGovernanceBadges from "../lib/components/IsoGovernanceBadges.svelte";
  import UploadModelsModal from "../lib/components/UploadModelsModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";

  interface Props {
    initialProjectId: number | null;
    onSelectProjectForViewer: (projectId: number) => void;
  }

  let { initialProjectId, onSelectProjectForViewer }: Props = $props();

  let files: ProjectIfcFile[] = $state([]);
  let isLoading = $state(true);
  let loadError = $state("");
  let sortField = $state("uploaded_at");
  let sortAsc = $state(false);
  let isUploadOpen = $state(false);
  let fileToDelete: ProjectIfcFile | null = $state(null);
  let isDeleteModalOpen = $state(false);
  let pendingActionId: number | null = $state(null);

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
      const result = await projectsApi.listIfcFiles(projectId);
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

  $effect(() => {
    if (initialProjectId) loadFiles(initialProjectId);
  });

  function handleSort(col: string) {
    if (sortField === col) {
      sortAsc = !sortAsc;
    } else {
      sortField = col;
      sortAsc = true;
    }
  }

  let sortedFiles = $derived(
    [...files].sort((a, b) => {
      // Primary always leads regardless of the chosen sort column — it's the
      // model every other view (Viewer, Compliance Audit) opens by default.
      if (a.is_primary !== b.is_primary) return a.is_primary ? -1 : 1;
      let cmp = 0;
      if (sortField === "file_name") {
        cmp = (a.file_name || "").localeCompare(b.file_name || "");
      } else if (sortField === "role") {
        cmp = (a.role || "").localeCompare(b.role || "");
      } else {
        cmp = (a.uploaded_at || "").localeCompare(b.uploaded_at || "");
      }
      return sortAsc ? cmp : -cmp;
    }),
  );

  function handleUploaded(updated: ProjectIfcFile[]) {
    files = updated;
    isUploadOpen = false;
  }

  async function handleSetPrimary(file: ProjectIfcFile) {
    if (!initialProjectId || file.id == null || file.is_primary) return;
    pendingActionId = file.id;
    try {
      await projectsApi.setPrimaryIfcFile(initialProjectId, file.id);
      files = await projectsApi.listIfcFiles(initialProjectId);
    } catch (err) {
      toasts.fromError(err, "Could not set this model as primary.");
    } finally {
      pendingActionId = null;
    }
  }

  function promptDelete(file: ProjectIfcFile) {
    fileToDelete = file;
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!initialProjectId || fileToDelete?.id == null) return;
    try {
      await projectsApi.deleteIfcFile(initialProjectId, fileToDelete.id);
      files = files.filter((f) => f.id !== fileToDelete!.id);
      toasts.success(`Removed "${fileToDelete.file_name}".`);
    } catch (err) {
      toasts.fromError(err, "Could not delete this model.");
    } finally {
      fileToDelete = null;
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
      <button
        type="button"
        onclick={() => (isUploadOpen = true)}
        disabled={!initialProjectId}
        class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        <UploadCloud class="h-3.5 w-3.5" />
        <span>Attach Model</span>
      </button>
    {/snippet}
  </PageHeader>

  <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
    {#if isLoading}
      <LoadingState message="Loading models…" />
    {:else if loadError}
      <div class="rounded-xl border border-rose-800/60 bg-rose-950/40 p-4 text-xs text-rose-300">
        {loadError}
      </div>
    {:else if sortedFiles.length === 0}
      <EmptyState
        icon={Boxes}
        title="No models attached"
        description="Attach an IFC model to make this project ready for the 3D Viewer and Compliance Audit."
        actionLabel="Attach Model"
        onAction={() => (isUploadOpen = true)}
      />
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead class="border-b border-slate-800">
            <tr>
              <SortHeader column="file_name" {sortField} {sortAsc} onSort={handleSort}
                >File</SortHeader
              >
              <SortHeader column="role" {sortField} {sortAsc} onSort={handleSort}
                >Role</SortHeader
              >
              <th class="px-4 py-3 text-caption font-semibold uppercase tracking-wider text-slate-400"
                >ISO 19650</th
              >
              <SortHeader column="uploaded_at" {sortField} {sortAsc} onSort={handleSort}
                >Uploaded</SortHeader
              >
              <th
                class="px-4 py-3 text-right text-caption font-semibold uppercase tracking-wider text-slate-400"
                >Actions</th
              >
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each sortedFiles as file (file.id ?? file.file_path)}
              <tr class="transition-colors hover:bg-slate-900/60">
                <td class="max-w-xs truncate px-4 py-3 font-semibold text-slate-50">
                  {file.file_name}
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
                  {file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : "—"}
                </td>
                <td class="px-4 py-3 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      onclick={() =>
                        initialProjectId && onSelectProjectForViewer(initialProjectId)}
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
    {/if}
  </div>
</div>

<UploadModelsModal
  isOpen={isUploadOpen}
  projectId={initialProjectId}
  onClose={() => (isUploadOpen = false)}
  onUploaded={handleUploaded}
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
