<script lang="ts">
  import { CheckSquare, Trash2, Pencil, Download, X } from "lucide-svelte";

  interface Props {
    selectedCount?: number;
    itemLabel?: string;
    onClearSelection: () => void;
    onBulkDelete?: (() => void) | null;
    onBulkEdit?: (() => void) | null;
    onBulkExport?: (() => void) | null;
    children?: import("svelte").Snippet;
  }

  let {
    selectedCount = 0,
    itemLabel = "item",
    onClearSelection,
    onBulkDelete = null,
    onBulkEdit = null,
    onBulkExport = null,
    children,
  }: Props = $props();
</script>

{#if selectedCount > 0}
  <div
    class="apple-blur flex items-center justify-between gap-4 rounded-xl border border-blue-800/80 bg-blue-950/80 px-4 py-2.5 text-xs text-blue-200 shadow-lg shadow-blue-950/40 duration-200 animate-in fade-in slide-in-from-top-2"
  >
    <div class="flex items-center gap-2.5 font-medium">
      <CheckSquare class="h-4 w-4 shrink-0 text-blue-400" />
      <span>
        <strong class="font-bold text-slate-50">{selectedCount}</strong>
        {itemLabel}{selectedCount === 1 ? "" : "s"} selected
      </span>
    </div>

    <div class="flex items-center gap-2">
      {@render children?.()}

      {#if onBulkEdit}
        <button
          type="button"
          onclick={onBulkEdit}
          class="inline-flex items-center gap-1.5 rounded-lg border border-blue-500/40 bg-blue-600/30 px-3 py-1.5 font-semibold text-blue-200 transition-all hover:bg-blue-600/50"
        >
          <Pencil class="h-3.5 w-3.5" />
          <span>Edit</span>
        </button>
      {/if}

      {#if onBulkExport}
        <button
          type="button"
          onclick={onBulkExport}
          class="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 font-semibold text-slate-200 transition-all hover:bg-slate-700"
        >
          <Download class="h-3.5 w-3.5" />
          <span>Export</span>
        </button>
      {/if}

      {#if onBulkDelete}
        <button
          type="button"
          onclick={onBulkDelete}
          class="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-600/30 px-3 py-1.5 font-semibold text-rose-200 transition-all hover:bg-rose-600/50"
        >
          <Trash2 class="h-3.5 w-3.5" />
          <span>Delete</span>
        </button>
      {/if}

      <div class="mx-1 h-4 w-px bg-blue-800/80"></div>

      <button
        type="button"
        onclick={onClearSelection}
        class="rounded-lg p-1 text-blue-300 transition-colors hover:bg-blue-900/60 hover:text-slate-50"
        title="Clear selection"
      >
        <X class="h-4 w-4" />
      </button>
    </div>
  </div>
{/if}
