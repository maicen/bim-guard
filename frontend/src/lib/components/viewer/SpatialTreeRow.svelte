<script lang="ts">
  import { ChevronRight, ChevronDown } from "lucide-svelte";
  import type { SpatialTreeNodeContract } from "../../types";
  import SpatialTreeRow from "./SpatialTreeRow.svelte";

  let {
    node,
    depth = 0,
    selectedGuid = null,
    onSelect,
  }: {
    node: SpatialTreeNodeContract;
    depth?: number;
    /** guid of the currently selected node, for highlighting. */
    selectedGuid?: string | null;
    /** Called with a node when its label is clicked, to inspect its graph relationships. */
    onSelect?: (node: SpatialTreeNodeContract) => void;
  } = $props();

  // Project/Site/Building open by default so the tree isn't a single collapsed
  // root on first render; storeys and deeper stay collapsed until expanded.
  let userExpanded = $state<boolean | null>(null);
  const isExpanded = $derived(userExpanded !== null ? userExpanded : depth < 3);
  const isSelected = $derived(selectedGuid === node.guid);
</script>

<div>
  <div
    class="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-fg-secondary hover:bg-surface-hover {isSelected
      ? 'bg-surface-selected text-fg-primary'
      : ''}"
    style:padding-left="{0.5 + depth * 1.25}rem"
  >
    {#if node.children.length > 0}
      <button
        type="button"
        onclick={() => (userExpanded = !isExpanded)}
        class="shrink-0 text-fg-muted hover:text-fg-primary"
        aria-label={isExpanded ? "Collapse" : "Expand"}
      >
        {#if isExpanded}
          <ChevronDown class="h-3.5 w-3.5" />
        {:else}
          <ChevronRight class="h-3.5 w-3.5" />
        {/if}
      </button>
    {:else}
      <span class="w-3.5 shrink-0"></span>
    {/if}
    <button
      type="button"
      onclick={() => onSelect?.(node)}
      class="flex-1 truncate text-left"
    >
      {node.label}
    </button>
    <span class="shrink-0 rounded border border-border-default px-1 text-[10px] text-fg-muted">
      {node.ifc_type}
    </span>
  </div>
  {#if node.children.length > 0 && isExpanded}
    {#each node.children as child (child.guid)}
      <SpatialTreeRow node={child} depth={depth + 1} {selectedGuid} {onSelect} />
    {/each}
    {#if node.truncated_count > 0}
      <div
        class="text-[10px] text-fg-muted"
        style:padding-left="{0.5 + (depth + 1) * 1.25 + 1.25}rem"
      >
        +{node.truncated_count} more not shown
      </div>
    {/if}
  {/if}
</div>
