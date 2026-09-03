<script lang="ts">
  import { CheckSquare, Trash2, Pencil, Download, X } from "lucide-svelte";

  export let selectedCount: number = 0;
  export let itemLabel: string = "item";
  export let onClearSelection: () => void;
  export let onBulkDelete: (() => void) | null = null;
  export let onBulkEdit: (() => void) | null = null;
  export let onBulkExport: (() => void) | null = null;
</script>

{#if selectedCount > 0}
  <div
    class="flex items-center justify-between gap-4 px-4 py-2.5 rounded-xl bg-blue-950/80 border border-blue-800/80 text-xs text-blue-200 apple-blur shadow-lg shadow-blue-950/40 animate-in fade-in slide-in-from-top-2 duration-200"
  >
    <div class="flex items-center gap-2.5 font-medium">
      <CheckSquare class="w-4 h-4 text-blue-400 shrink-0" />
      <span>
        <strong class="text-slate-50 font-bold">{selectedCount}</strong>
        {itemLabel}{selectedCount === 1 ? "" : "s"} selected
      </span>
    </div>

    <div class="flex items-center gap-2">
      {#if onBulkEdit}
        <button
          type="button"
          on:click={onBulkEdit}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600/30 hover:bg-blue-600/50 text-blue-200 border border-blue-500/40 font-semibold transition-all"
        >
          <Pencil class="w-3.5 h-3.5" />
          <span>Edit</span>
        </button>
      {/if}

      {#if onBulkExport}
        <button
          type="button"
          on:click={onBulkExport}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold transition-all"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Export</span>
        </button>
      {/if}

      {#if onBulkDelete}
        <button
          type="button"
          on:click={onBulkDelete}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 border border-rose-500/40 font-semibold transition-all"
        >
          <Trash2 class="w-3.5 h-3.5" />
          <span>Delete</span>
        </button>
      {/if}

      <div class="h-4 w-px bg-blue-800/80 mx-1"></div>

      <button
        type="button"
        on:click={onClearSelection}
        class="p-1 rounded-lg hover:bg-blue-900/60 text-blue-300 hover:text-slate-50 transition-colors"
        title="Clear selection"
      >
        <X class="w-4 h-4" />
      </button>
    </div>
  </div>
{/if}
