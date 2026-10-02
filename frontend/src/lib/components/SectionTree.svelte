<script lang="ts">
  import {
    Search,
    ChevronDown,
    ChevronRight,
    ChevronsUpDown,
    Filter,
    Box,
    X,
    Eye,
    CheckSquare,
    Square,
  } from "lucide-svelte";
  import type { SectionTreeNode } from "../types";
  import SectionTreeRow from "./SectionTreeRow.svelte";
  import Select from "./ui/Select.svelte";

  let {
    nodes,
    selected,
    depth = 0,
    query = $bindable(""),
    forceExpanded = null,
    onViewSource,
  }: {
    nodes: SectionTreeNode[];
    /** Mutated directly (leaf section ids) — shared by reference with the caller. */
    selected: Set<string>;
    depth?: number;
    /** Lowercased search text; the input box only renders at depth 0, then flows to every level. */
    query?: string;
    /** Controlled expansion override (e.g. from Expand All / Collapse All buttons). */
    forceExpanded?: boolean | null;
    /** When given, shows a "view in document" icon for nodes with a known page_number. */
    onViewSource?: (node: SectionTreeNode) => void;
  } = $props();

  // Filter states only active at depth 0
  let hideFrontMatter = $state(true);
  let onlyIfcClasses = $state(false);
  let selectedChapter = $state("all");
  let controlledExpanded = $state<boolean | null>(null);

  const effectiveExpanded = $derived(
    depth === 0 ? controlledExpanded : forceExpanded
  );

  function isFrontMatter(node: SectionTreeNode): boolean {
    if (node.section_number) return false;
    const name = (node.section_name || "").toLowerCase();
    const isPreambleWord =
      /^(gratitude|committee|preface|table of contents|contents|dedication|acknowledgements?|index|consultative|sub\s*-\s*committee|national committee)\b/i.test(
        name
      );
    const isEarlyPage = node.page_number !== null && node.page_number !== undefined && node.page_number <= 20;
    return isPreambleWord || isEarlyPage;
  }

  function nodeMatchesText(node: SectionTreeNode, q: string): boolean {
    if (!q) return true;
    const textMatch =
      (node.section_number ?? "").toLowerCase().includes(q) ||
      (node.section_name ?? "").toLowerCase().includes(q) ||
      (node.summary ?? "").toLowerCase().includes(q);
    const topicMatch = node.key_topics?.some((t) => t.toLowerCase().includes(q)) ?? false;
    const ifcMatch = node.target_ifc_classes?.some((c) => c.toLowerCase().includes(q)) ?? false;
    const citationMatch = node.citations?.some((c) => c.toLowerCase().includes(q)) ?? false;
    return Boolean(textMatch || topicMatch || ifcMatch || citationMatch);
  }

  function pruneTree(list: SectionTreeNode[], q: string): SectionTreeNode[] {
    const result: SectionTreeNode[] = [];
    for (const node of list) {
      if (depth === 0 && hideFrontMatter && isFrontMatter(node)) {
        continue;
      }
      if (depth === 0 && onlyIfcClasses && (!node.target_ifc_classes || node.target_ifc_classes.length === 0)) {
        // Check if any descendant has IFC classes
        const hasDescendantIfc = (n: SectionTreeNode): boolean =>
          (n.target_ifc_classes && n.target_ifc_classes.length > 0) ||
          n.children.some(hasDescendantIfc);
        if (!hasDescendantIfc(node)) continue;
      }
      if (depth === 0 && selectedChapter !== "all") {
        const matchesChapter =
          node.section_number === selectedChapter ||
          node.section_number?.startsWith(`${selectedChapter}.`) ||
          (node.section_name || "").toLowerCase().includes(`chapter ${selectedChapter.toLowerCase()}`) ||
          (node.section_name || "").toLowerCase().includes(`section ${selectedChapter.toLowerCase()}`);
        if (!matchesChapter) continue;
      }

      const prunedChildren = pruneTree(node.children, q);
      if (nodeMatchesText(node, q) || prunedChildren.length > 0) {
        result.push(
          prunedChildren.length === node.children.length ? node : { ...node, children: prunedChildren }
        );
      }
    }
    return result;
  }

  const trimmedQuery = $derived(query.trim().toLowerCase());
  const visibleNodes = $derived(
    depth === 0
      ? pruneTree(nodes, trimmedQuery)
      : trimmedQuery
        ? pruneTree(nodes, trimmedQuery)
        : nodes
  );

  // Extract top-level chapters for the chapter filter dropdown
  const availableChapters = $derived.by(() => {
    if (depth !== 0) return [];
    const chapters: { id: string; label: string }[] = [];
    for (const n of nodes) {
      if (n.section_number && !n.section_number.includes(".")) {
        chapters.push({
          id: n.section_number,
          label: n.section_name ? `${n.section_number} — ${n.section_name}` : `Chapter ${n.section_number}`,
        });
      }
    }
    return chapters;
  });

  function countAllLeafs(list: SectionTreeNode[]): string[] {
    return list.flatMap((n) => (n.children.length === 0 ? [n.id] : countAllLeafs(n.children)));
  }

  const visibleLeafIds = $derived(countAllLeafs(visibleNodes));

  function selectVisible() {
    for (const id of visibleLeafIds) {
      selected.add(id);
    }
  }

  function clearVisible() {
    for (const id of visibleLeafIds) {
      selected.delete(id);
    }
  }
</script>

{#if depth === 0}
  <div class="space-y-2 mb-2">
    <!-- Search Bar -->
    <div class="relative flex items-center">
      <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-muted" />
      <input
        type="text"
        bind:value={query}
        placeholder="Filter sections by number, title, IFC class, or topic…"
        class="w-full rounded-lg border border-border-default bg-surface-canvas py-1.5 pl-8 pr-8 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
      />
      {#if query}
        <button
          type="button"
          onclick={() => (query = "")}
          class="absolute right-2.5 top-1/2 -translate-y-1/2 text-fg-muted hover:text-fg-primary"
          title="Clear filter"
        >
          <X class="h-3.5 w-3.5" />
        </button>
      {/if}
    </div>

    <!-- Quick Filter & View Options Toolbar -->
    <div class="flex flex-wrap items-center justify-between gap-2 text-micro">
      <!-- Left: Filters -->
      <div class="flex flex-wrap items-center gap-2">
        <label class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border-default bg-surface-canvas px-2 py-1 text-fg-secondary hover:bg-surface-hover select-none">
          <input
            type="checkbox"
            bind:checked={hideFrontMatter}
            class="h-3 w-3 rounded border-border-interactive accent-accent"
          />
          <span>Hide Front Matter</span>
        </label>

        <label class="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border-default bg-surface-canvas px-2 py-1 text-fg-secondary hover:bg-surface-hover select-none">
          <input
            type="checkbox"
            bind:checked={onlyIfcClasses}
            class="h-3 w-3 rounded border-border-interactive accent-accent"
          />
          <Box class="h-2.5 w-2.5 text-accent" />
          <span>Has IFC Mappings</span>
        </label>

        {#if availableChapters.length > 0}
          <div class="inline-flex items-center gap-1 rounded-md border border-border-default bg-surface-canvas px-1.5 py-0.5">
            <span class="text-fg-muted text-[10px]">Chapter:</span>
            <Select
              bind:value={selectedChapter}
              options={[{ value: "all", label: "All" }, ...availableChapters.map((ch) => ({ value: ch.id, label: ch.label.slice(0, 32) }))]}
              ariaLabel="Filter by chapter"
              triggerClass="h-6 w-auto min-w-24 rounded-md border-0 bg-transparent px-1 py-0 text-micro shadow-none"
            />
          </div>
        {/if}
      </div>

      <!-- Right: Expansion & Selection Helpers -->
      <div class="flex items-center gap-1.5 shrink-0">
        <div class="inline-flex rounded-md border border-border-default bg-surface-canvas p-0.5">
          <button
            type="button"
            onclick={() => (controlledExpanded = true)}
            class="rounded px-1.5 py-0.5 text-micro font-medium text-fg-muted hover:text-fg-primary hover:bg-surface-hover transition-colors"
            title="Expand all outline levels"
          >
            Expand All
          </button>
          <span class="text-border-default select-none">|</span>
          <button
            type="button"
            onclick={() => (controlledExpanded = false)}
            class="rounded px-1.5 py-0.5 text-micro font-medium text-fg-muted hover:text-fg-primary hover:bg-surface-hover transition-colors"
            title="Collapse all outline levels"
          >
            Collapse All
          </button>
        </div>

        <button
          type="button"
          onclick={selectVisible}
          class="rounded-md border border-border-default bg-surface-canvas px-2 py-1 text-micro font-medium text-accent hover:bg-surface-hover transition-colors"
          title="Select all currently visible clauses"
        >
          Select Visible ({visibleLeafIds.length})
        </button>
      </div>
    </div>
  </div>
{/if}

<div class="space-y-0.5" class:mt-2={depth === 0}>
  {#if visibleNodes.length === 0}
    <div class="rounded-lg border border-dashed border-border-default p-4 text-center text-xs text-fg-muted">
      No clauses match the current filter or search criteria.
      {#if hideFrontMatter || onlyIfcClasses || selectedChapter !== "all" || query}
        <button
          type="button"
          onclick={() => {
            query = "";
            hideFrontMatter = false;
            onlyIfcClasses = false;
            selectedChapter = "all";
          }}
          class="ml-1 font-semibold text-accent hover:underline"
        >
          Reset filters
        </button>
      {/if}
    </div>
  {:else}
    {#each visibleNodes as node (node.id)}
      <SectionTreeRow
        {node}
        {selected}
        {depth}
        query={trimmedQuery}
        forceExpanded={effectiveExpanded}
        {onViewSource}
      />
    {/each}
  {/if}
</div>
