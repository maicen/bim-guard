<script lang="ts">
  import { graphApi } from "../../api";
  import type { SpatialTreeNodeContract } from "../../types";
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
</script>

<div class="p-2 text-xs">
  {#if loading}
    <LoadingState message="Loading spatial hierarchy…" />
  {:else if error}
    <p class="p-2 text-critical">{error}</p>
  {:else if !root}
    <p class="p-2 text-fg-muted">No spatial hierarchy available for this model.</p>
  {:else}
    <SpatialTreeRow node={root} />
  {/if}
</div>
