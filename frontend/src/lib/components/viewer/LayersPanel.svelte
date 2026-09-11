<script lang="ts">
  import { onDestroy } from "svelte";

  let { viewerAPI }: { viewerAPI: any } = $props();

  let layers: { name: string; visible: boolean }[] = $state([]);

  function refresh() {
    if (!viewerAPI) return;
    layers = viewerAPI.layers.list();
  }

  let unsubscribe: (() => void) | undefined;
  $effect(() => {
    if (!viewerAPI) return;
    refresh();
    unsubscribe = viewerAPI.layers.onChange(refresh);
  });

  onDestroy(() => unsubscribe?.());

  function toggle(name: string, visible: boolean) {
    viewerAPI.layers.toggle(name, visible);
  }
</script>

<div class="p-2 text-xs">
  {#if layers.length === 0}
    <p class="p-2 text-slate-500">No categories yet — load a model first.</p>
  {:else}
    <ul class="space-y-0.5">
      {#each layers as layer (layer.name)}
        <li>
          <label
            class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-800/60"
          >
            <input
              type="checkbox"
              checked={layer.visible}
              onchange={(e) => toggle(layer.name, (e.target as HTMLInputElement).checked)}
              class="h-3.5 w-3.5 rounded border-slate-600 bg-slate-800 text-accent"
            />
            <span class="truncate text-slate-300">{layer.name}</span>
          </label>
        </li>
      {/each}
    </ul>
  {/if}
</div>
