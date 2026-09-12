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
    class="apple-blur flex items-center justify-between gap-4 rounded-xl border border-accent/40 bg-surface-card/95 px-4 py-2.5 text-xs text-fg-primary shadow-xl ring-1 ring-accent/20 duration-200 animate-in fade-in slide-in-from-top-2"
  >
    <div class="flex items-center gap-2.5 font-medium">
      <CheckSquare class="h-4 w-4 shrink-0 text-accent" />
      <span>
        <strong class="font-bold text-fg-primary">{selectedCount}</strong>
        {itemLabel}{selectedCount === 1 ? "" : "s"} selected
      </span>
    </div>

    <div class="flex items-center gap-2">
      {@render children?.()}

      {#if onBulkEdit}
        <button
          type="button"
          onclick={onBulkEdit}
          class="inline-flex items-center gap-1.5 rounded-lg border border-accent/40 bg-accent/15 px-3 py-1.5 font-semibold text-accent transition-all hover:bg-accent/25"
        >
          <Pencil class="h-3.5 w-3.5" />
          <span>Edit</span>
        </button>
      {/if}

      {#if onBulkExport}
        <button
          type="button"
          onclick={onBulkExport}
          class="inline-flex items-center gap-1.5 rounded-lg border border-border-default bg-surface-hover/80 px-3 py-1.5 font-semibold text-fg-secondary transition-all hover:bg-surface-hover hover:text-fg-primary"
        >
          <Download class="h-3.5 w-3.5" />
          <span>Export</span>
        </button>
      {/if}

      {#if onBulkDelete}
        <button
          type="button"
          onclick={onBulkDelete}
          class="inline-flex items-center gap-1.5 rounded-lg border border-critical-border/60 bg-critical-bg/80 px-3 py-1.5 font-semibold text-critical transition-all hover:bg-critical-bg"
        >
          <Trash2 class="h-3.5 w-3.5" />
          <span>Delete</span>
        </button>
      {/if}

      <div class="mx-1 h-4 w-px bg-border-default"></div>

      <button
        type="button"
        onclick={onClearSelection}
        class="rounded-lg p-1 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
        title="Clear selection"
      >
        <X class="h-4 w-4" />
      </button>
    </div>
  </div>
{/if}
