<script lang="ts">
  import { Boxes } from "lucide-svelte";
  import { graphApi } from "../../api";
  import type { ElementRelationshipsResponse, SpatialTreeNodeContract } from "../../types";
  import LoadingState from "../LoadingState.svelte";
  import SpatialTreeRow from "./SpatialTreeRow.svelte";

  let { projectId }: { projectId: number | null } = $props();

  let root: SpatialTreeNodeContract | null = $state(null);
  let loading = $state(false);
  let error: string | null = $state(null);

  async function load(id: number) {
    loading = true;
    error = null;
    try {
      const res = await graphApi.getSpatialTree(id);
      root = res.root;
    } catch (err: any) {
      error = err?.message || "Failed to load the spatial hierarchy";
      root = null;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (projectId) load(projectId);
  });

  // Selecting a tree node (rather than clicking in the 3D viewport, which
  // this viewer has no element-picking wired up for yet) is how this panel
  // shows an element's BOT/SAREF4BLDG relationships -- the Knowledge
  // Graph-Enriched 3D Viewport, scoped to what's actually selectable today.
  let selectedNode: SpatialTreeNodeContract | null = $state(null);
  let relationships: ElementRelationshipsResponse | null = $state(null);
  let isLoadingRelationships = $state(false);
  let relationshipsError = $state("");

  async function selectNode(node: SpatialTreeNodeContract) {
    selectedNode = node;
    if (!projectId) return;
    isLoadingRelationships = true;
    relationshipsError = "";
    relationships = null;
    try {
      relationships = await graphApi.getElementRelationships(projectId, node.guid);
    } catch (err: any) {
      relationshipsError = err?.message || "Could not load this element's relationships.";
    } finally {
      isLoadingRelationships = false;
    }
  }
</script>

<div class="flex h-full flex-col text-xs">
  <div class="min-h-0 flex-1 overflow-auto p-2">
    {#if loading}
      <LoadingState message="Loading spatial hierarchy…" />
    {:else if error}
      <p class="p-2 text-critical">{error}</p>
    {:else if !root}
      <p class="p-2 text-fg-muted">No spatial hierarchy available for this model.</p>
    {:else}
      <SpatialTreeRow node={root} selectedGuid={selectedNode?.guid ?? null} onSelect={selectNode} />
    {/if}
  </div>

  {#if selectedNode}
    <div class="max-h-64 shrink-0 overflow-auto border-t border-border-default p-3">
      <div class="mb-2 flex items-center gap-1.5 font-semibold text-fg-primary">
        <Boxes class="h-3.5 w-3.5 text-accent" />
        <span class="truncate">{selectedNode.label}</span>
      </div>
      {#if isLoadingRelationships}
        <LoadingState message="Loading relationships…" />
      {:else if relationshipsError}
        <p class="text-critical">{relationshipsError}</p>
      {:else if relationships && !relationships.exists}
        <p class="text-fg-muted">Not found in the model's relationship graph.</p>
      {:else if relationships}
        {#if relationships.bot_classes.length || relationships.s4bldg_classes.length}
          <div class="mb-2 flex flex-wrap gap-1">
            {#each relationships.bot_classes as cls (cls)}
              <span class="rounded border border-info-border bg-info-bg px-1.5 py-0.5 text-[10px] text-info">
                bot:{cls}
              </span>
            {/each}
            {#each relationships.s4bldg_classes as cls (cls)}
              <span class="rounded border border-success-border bg-success-bg px-1.5 py-0.5 text-[10px] text-success">
                s4bldg:{cls}
              </span>
            {/each}
          </div>
        {/if}
        {#if relationships.incoming.length}
          <div class="mb-2">
            <div class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">
              Incoming
            </div>
            <ul class="space-y-0.5">
              {#each relationships.incoming as edge (edge.predicate + edge.guid)}
                <li class="flex items-center gap-1.5 text-fg-secondary">
                  <span class="font-mono text-[10px] text-fg-muted">{edge.predicate}</span>
                  <span class="truncate">{edge.label}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}
        {#if relationships.outgoing.length}
          <div>
            <div class="mb-1 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">
              Outgoing
            </div>
            <ul class="space-y-0.5">
              {#each relationships.outgoing as edge (edge.predicate + edge.guid)}
                <li class="flex items-center gap-1.5 text-fg-secondary">
                  <span class="font-mono text-[10px] text-fg-muted">{edge.predicate}</span>
                  <span class="truncate">{edge.label}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}
        {#if !relationships.incoming.length && !relationships.outgoing.length}
          <p class="text-fg-muted">No BOT/SAREF4BLDG relationships found.</p>
        {/if}
      {/if}
    </div>
  {/if}
</div>
