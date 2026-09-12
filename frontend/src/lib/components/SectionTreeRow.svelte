<script lang="ts">
  import { ChevronRight, ChevronDown, Eye, Table2 } from "lucide-svelte";
  import type { SectionTreeNode } from "../types";
  import TableCheckbox from "./TableCheckbox.svelte";
  import SectionTree from "./SectionTree.svelte";

  let {
    node,
    selected,
    depth,
    query = "",
    onViewSource,
  }: {
    node: SectionTreeNode;
    /** Mutated directly (leaf section ids) — shared by reference with the caller. */
    selected: Set<string>;
    depth: number;
    /** Already-trimmed/lowercased filter text, forces this row open while active. */
    query?: string;
    /** When given, shows a "view in document" icon for nodes with a known page_number or bbox. */
    onViewSource?: (node: SectionTreeNode) => void;
  } = $props();

  // Top-level chapters open by default; deeper clauses stay collapsed until
  // the user expands them (or a filter match forces every branch open).
  let userExpanded = $state<boolean | null>(null);
  const isExpanded = $derived(query !== "" || (userExpanded !== null ? userExpanded : depth === 0));

  function allLeafIds(n: SectionTreeNode): string[] {
    if (n.children.length === 0) return [n.id];
    return n.children.flatMap(allLeafIds);
  }

  const leafIds = $derived(allLeafIds(node));
  const selectionState = $derived.by(() => {
    const selectedCount = leafIds.filter((id) => selected.has(id)).length;
    if (selectedCount === 0) return "unchecked";
    if (selectedCount === leafIds.length) return "checked";
    return "indeterminate";
  });

  function toggle() {
    const shouldSelect = selectionState !== "checked";
    for (const id of leafIds) {
      if (shouldSelect) selected.add(id);
      else selected.delete(id);
    }
  }
</script>

<div>
  <label
    class="flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-900"
    style:padding-left="{0.5 + depth * 1.25}rem"
  >
    {#if node.children.length > 0}
      <button
        type="button"
        onclick={(event) => {
          event.preventDefault();
          userExpanded = !isExpanded;
        }}
        class="shrink-0 text-slate-500 hover:text-slate-300"
        aria-label={isExpanded ? "Collapse section" : "Expand section"}
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
    <TableCheckbox
      checked={selectionState === "checked"}
      indeterminate={selectionState === "indeterminate"}
      onchange={toggle}
      ariaLabel={`Select section ${node.section_number || node.id}`}
    />
    <span class="font-mono text-slate-500">{node.section_number || "—"}</span>
    <span class="flex-1 truncate">{node.section_name || "Untitled section"}</span>
    {#if node.node_type === "table"}
      <span
        class="inline-flex items-center gap-1 rounded bg-doc-table/15 border border-doc-table/40 px-1.5 py-0.5 text-[10px] font-semibold text-doc-table shrink-0"
        title="DocLang OTSL Table"
      >
        <Table2 class="h-3 w-3" />
        <span>Table</span>
      </span>
    {/if}
    {#if node.page_number}
      <span class="shrink-0 rounded border border-slate-800 px-1 text-slate-500">p. {node.page_number}</span>
    {/if}
    <span class="shrink-0 text-slate-600">{node.char_count.toLocaleString()} chars</span>
    {#if onViewSource && (node.page_number || node.bbox)}
      <button
        type="button"
        onclick={(event) => {
          event.preventDefault();
          onViewSource?.(node);
        }}
        class="shrink-0 rounded p-0.5 text-slate-500 hover:bg-slate-800 hover:text-slate-200"
        title="View this section in the document"
      >
        <Eye class="h-3.5 w-3.5" />
      </button>
    {/if}
  </label>
  {#if node.children.length > 0 && isExpanded}
    <SectionTree nodes={node.children} {selected} depth={depth + 1} {query} {onViewSource} />
  {/if}
</div>
