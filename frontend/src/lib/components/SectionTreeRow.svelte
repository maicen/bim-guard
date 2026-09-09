<script lang="ts">
  import { ChevronRight, ChevronDown } from "lucide-svelte";
  import type { SectionTreeNode } from "../types";
  import TableCheckbox from "./TableCheckbox.svelte";
  import SectionTree from "./SectionTree.svelte";

  let {
    node,
    selected,
    depth,
    query = "",
  }: {
    node: SectionTreeNode;
    /** Mutated directly (leaf section ids) — shared by reference with the caller. */
    selected: Set<string>;
    depth: number;
    /** Already-trimmed/lowercased filter text, forces this row open while active. */
    query?: string;
  } = $props();

  // Top-level chapters open by default; deeper clauses stay collapsed until
  // the user expands them (or a filter match forces every branch open).
  let localExpanded = $state(depth === 0);
  const isExpanded = $derived(query !== "" || localExpanded);

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
          localExpanded = !localExpanded;
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
    <span class="shrink-0 text-slate-600">{node.char_count.toLocaleString()} chars</span>
  </label>
  {#if node.children.length > 0 && isExpanded}
    <SectionTree nodes={node.children} {selected} depth={depth + 1} {query} />
  {/if}
</div>
