<script lang="ts">
  import { Search } from "lucide-svelte";
  import type { SectionTreeNode } from "../types";
  import SectionTreeRow from "./SectionTreeRow.svelte";

  let {
    nodes,
    selected,
    depth = 0,
    query = $bindable(""),
    onViewSource,
  }: {
    nodes: SectionTreeNode[];
    /** Mutated directly (leaf section ids) — shared by reference with the caller. */
    selected: Set<string>;
    depth?: number;
    /** Lowercased search text; the input box only renders at depth 0, then flows to every level. */
    query?: string;
    /** When given, shows a "view in document" icon for nodes with a known page_number. */
    onViewSource?: (node: SectionTreeNode) => void;
  } = $props();

  function nodeMatches(node: SectionTreeNode, q: string): boolean {
    return (
      (node.section_number ?? "").toLowerCase().includes(q) ||
      (node.section_name ?? "").toLowerCase().includes(q)
    );
  }

  function pruneTree(list: SectionTreeNode[], q: string): SectionTreeNode[] {
    const result: SectionTreeNode[] = [];
    for (const node of list) {
      const prunedChildren = pruneTree(node.children, q);
      if (nodeMatches(node, q) || prunedChildren.length > 0) {
        result.push(
          prunedChildren.length === node.children.length ? node : { ...node, children: prunedChildren },
        );
      }
    }
    return result;
  }

  const trimmedQuery = $derived(query.trim().toLowerCase());
  const visibleNodes = $derived(trimmedQuery ? pruneTree(nodes, trimmedQuery) : nodes);
</script>

{#if depth === 0}
  <label class="relative block">
    <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-muted" />
    <input
      type="text"
      bind:value={query}
      placeholder="Filter sections by number or title…"
      class="w-full rounded-lg border border-border-default bg-surface-canvas py-1.5 pl-8 pr-3 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
    />
  </label>
{/if}

<div class="space-y-0.5" class:mt-2={depth === 0}>
  {#each visibleNodes as node (node.id)}
    <SectionTreeRow {node} {selected} {depth} query={trimmedQuery} {onViewSource} />
  {/each}
</div>
