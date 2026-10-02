<script lang="ts">
  import { Download, ScanEye, Trash2, Search } from "lucide-svelte";
  import type { BcfArtifact, Project } from "../types";
  import type { TableState } from "../tableState.svelte";
  import TablePagination from "./TablePagination.svelte";
  import BulkActionBar from "./BulkActionBar.svelte";
  import SortHeader from "./SortHeader.svelte";
  import TableCheckbox from "./TableCheckbox.svelte";

  interface Props {
    artifacts: BcfArtifact[];
    tableState: TableState<BcfArtifact, number>;
    /** Short label used in headers, buttons and empty-state copy, e.g. "BCF", "PDF", "CSV". */
    typeLabel: string;
    /** Download button label/icon text, e.g. "Zip", "PDF", "CSV". */
    downloadLabel: string;
    projects: Project[];
    isLoading: boolean;
    selectedProjectId: number | null;
    filterToSelectedProject: boolean;
    onFilterToggle: (v: boolean) => void;
    onDownload: (artifact: BcfArtifact) => void;
    onDeleteOne: (artifact: BcfArtifact) => void;
    onBulkDelete: () => void;
    onBulkExport: () => void;
    /** Present only for the BCF tab -- PDF/CSV artifacts have no 3D viewpoints. */
    onViewIn3d?: ((artifact: BcfArtifact) => void) | undefined;
  }

  let {
    artifacts,
    tableState,
    typeLabel,
    downloadLabel,
    projects,
    isLoading,
    selectedProjectId,
    filterToSelectedProject,
    onFilterToggle,
    onDownload,
    onDeleteOne,
    onBulkDelete,
    onBulkExport,
    onViewIn3d = undefined,
  }: Props = $props();

  function getProjectName(projId: number): string {
    const p = projects.find((x) => x.id === projId);
    return p ? p.name : `Project #${projId}`;
  }

  function formatBytes(bytes?: number): string {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  }

  function formatDate(dateStr?: string): string {
    if (!dateStr) return "—";
    try {
      return new Date(dateStr).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return dateStr;
    }
  }

  let currentProject = $derived(projects.find((p) => p.id === selectedProjectId));
</script>

<!-- Filters & Project Filter Toolbar -->
<div
  class="flex flex-col items-center justify-between gap-3 rounded-2xl border border-border-default/90 bg-surface-canvas/80 p-3.5 sm:flex-row"
>
  <div class="relative w-full flex-1">
    <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
    <input
      type="text"
      bind:value={tableState.search}
      placeholder={`Filter ${typeLabel} reports by filename or project...`}
      class="w-full rounded-xl border border-border-default bg-surface-card py-2 pl-10 pr-4 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
    />
  </div>

  {#if selectedProjectId}
    <div class="flex items-center rounded-xl border border-border-default bg-surface-card p-1 text-xs">
      <button
        type="button"
        onclick={() => onFilterToggle(false)}
        class="rounded-lg px-2.5 py-1 font-medium transition-colors {!filterToSelectedProject
          ? 'bg-surface-overlay text-fg-primary'
          : 'text-fg-muted hover:text-fg-primary'}"
      >
        All Projects
      </button>
      <button
        type="button"
        onclick={() => onFilterToggle(true)}
        class="rounded-lg px-2.5 py-1 font-medium transition-colors {filterToSelectedProject
          ? 'bg-blue-600 text-white'
          : 'text-fg-muted hover:text-fg-primary'}"
      >
        {currentProject?.name || "Selected"}
      </button>
    </div>
  {/if}
</div>

<!-- Bulk Action Bar -->
<BulkActionBar
  selectedCount={tableState.selectedCount}
  itemLabel={`${typeLabel} artifact`}
  onClearSelection={() => tableState.clearSelection()}
  onBulkExport={onBulkExport}
  onBulkDelete={onBulkDelete}
/>

{#if isLoading && artifacts.length === 0}
  <div class="p-12 text-center text-xs text-fg-muted">
    <div class="mx-auto mb-2 h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"></div>
    Loading {typeLabel} artifacts…
  </div>
{:else if tableState.totalItems === 0}
  <div class="rounded-xl border border-dashed border-border-default p-12 text-center text-xs text-fg-muted">
    {filterToSelectedProject
      ? `No ${typeLabel} reports found for ${currentProject?.name || "this project"}. Run a Compliance Audit to generate one.`
      : `No persisted ${typeLabel} artifacts found matching your filter.`}
  </div>
{:else}
  <div class="overflow-x-auto rounded-xl border border-border-default">
    <table aria-label="Report artifacts" class="w-full border-collapse text-left text-xs">
      <thead>
        <tr class="border-b border-border-default bg-surface-canvas/60 text-micro font-semibold uppercase tracking-wider text-fg-muted">
          <th scope="col" class="w-10 px-4 py-3">
            <TableCheckbox
              checked={tableState.allFilteredSelected}
              indeterminate={tableState.someFilteredSelected}
              onchange={() => tableState.toggleSelectAll()}
              title={`Select all ${typeLabel} artifacts`}
            />
          </th>
          <SortHeader column="id" sortField={tableState.sortField} sortAsc={tableState.sortAsc} onSort={(f) => tableState.toggleSort(f)}>
            ID
          </SortHeader>
          <th scope="col" class="px-4 py-3">Project</th>
          <th scope="col" class="px-4 py-3">Ruleset</th>
          <th scope="col" class="px-4 py-3">User</th>
          <SortHeader column="filename" sortField={tableState.sortField} sortAsc={tableState.sortAsc} onSort={(f) => tableState.toggleSort(f)}>
            Artifact / Filename
          </SortHeader>
          <SortHeader column="issue_count" sortField={tableState.sortField} sortAsc={tableState.sortAsc} onSort={(f) => tableState.toggleSort(f)}>
            Issues
          </SortHeader>
          <SortHeader column="byte_size" sortField={tableState.sortField} sortAsc={tableState.sortAsc} onSort={(f) => tableState.toggleSort(f)}>
            Size
          </SortHeader>
          <SortHeader column="created_at" sortField={tableState.sortField} sortAsc={tableState.sortAsc} onSort={(f) => tableState.toggleSort(f)}>
            Date
          </SortHeader>
          <th scope="col" class="px-4 py-3 text-right">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-border-subtle">
        {#each tableState.paginated as artifact (artifact.id)}
          <tr class="transition-colors hover:bg-surface-hover {tableState.isSelected(artifact.id) ? 'bg-surface-selected' : ''} {tableState.isPending(artifact.id) ? 'opacity-50 pointer-events-none' : ''}">
            <td class="w-10 px-4 py-3">
              <TableCheckbox
                checked={tableState.isSelected(artifact.id)}
                onchange={() => tableState.toggleSelect(artifact.id)}
                ariaLabel={`Select artifact ${artifact.filename}`}
              />
            </td>
            <td class="px-4 py-3 font-mono text-fg-muted">#{artifact.id}</td>
            <td class="px-4 py-3 font-medium text-fg-primary">
              {getProjectName(artifact.project_id)}
              <div class="text-micro font-normal text-fg-muted">#{artifact.project_id}</div>
            </td>
            <td class="px-4 py-3">
              <div class="text-fg-secondary">{artifact.ruleset_name || "All Rules"}</div>
              {#if artifact.rule_folder}
                <div class="font-mono text-micro text-fg-muted">{artifact.rule_folder}</div>
              {/if}
            </td>
            <td class="px-4 py-3 text-fg-secondary">{artifact.created_by_email || "—"}</td>
            <td class="px-4 py-3">
              <div class="max-w-xs truncate font-mono text-fg-secondary" title={artifact.filename}>
                {artifact.filename}
              </div>
            </td>
            <td class="px-4 py-3">
              <span
                class="inline-block rounded-md border px-2.5 py-0.5 text-micro font-semibold {artifact.issue_count > 0
                  ? 'border-rose-800 bg-rose-950/60 text-rose-300'
                  : 'border-emerald-800 bg-emerald-950/60 text-emerald-300'}"
              >
                {artifact.issue_count} issue{artifact.issue_count === 1 ? "" : "s"}
              </span>
            </td>
            <td class="px-4 py-3 font-mono text-fg-muted">{formatBytes(artifact.byte_size)}</td>
            <td class="whitespace-nowrap px-4 py-3 text-fg-muted">{formatDate(artifact.created_at)}</td>
            <td class="px-4 py-3 text-right">
              <div class="inline-flex items-center justify-end gap-1.5">
                {#if onViewIn3d}
                  <button
                    type="button"
                    onclick={() => onViewIn3d?.(artifact)}
                    class="inline-flex items-center gap-1 rounded-lg border border-emerald-800 bg-emerald-900/40 px-2.5 py-1 text-xs font-semibold text-emerald-300 transition-colors hover:bg-emerald-800/60"
                    title="Open 3D Viewer with this BCF Report"
                  >
                    <ScanEye class="h-3.5 w-3.5" />
                    View 3D
                  </button>
                {/if}
                <button
                  type="button"
                  onclick={() => onDownload(artifact)}
                  class="inline-flex items-center gap-1 rounded-lg border border-blue-500/30 bg-blue-600/20 px-2.5 py-1 text-xs font-semibold text-blue-300 transition-colors hover:bg-blue-600/30"
                  title={`Download ${typeLabel}`}
                >
                  <Download class="h-3.5 w-3.5" />
                  {downloadLabel}
                </button>
                <button
                  type="button"
                  onclick={() => onDeleteOne(artifact)}
                  class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                  title={`Delete ${typeLabel} archive`}
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
    currentPage={tableState.page}
    pageSize={tableState.pageSize}
    totalItems={tableState.totalItems}
    onPageChange={(p) => (tableState.requestedPage = p)}
    onPageSizeChange={(size) => {
      tableState.pageSize = size;
      tableState.requestedPage = 1;
    }}
  />
{/if}
