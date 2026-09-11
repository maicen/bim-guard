<script lang="ts">
  import { onDestroy } from "svelte";

  let {
    viewerAPI,
    sheetBoardHost = $bindable<HTMLDivElement | undefined>(undefined),
  }: { viewerAPI: any; sheetBoardHost?: HTMLDivElement } = $props();

  let drawings: { id: string; label: string }[] = $state([]);
  let activeDrawingId: string | null = $state(null);
  let activeLayers: { name: string; visible: boolean; color: string }[] = $state([]);

  function refresh() {
    if (!viewerAPI) return;
    drawings = viewerAPI.drawings.list();
    activeDrawingId = viewerAPI.drawings.activeId();
    activeLayers = viewerAPI.drawings.activeLayers();
  }

  let unsubscribe: (() => void) | undefined;
  $effect(() => {
    if (!viewerAPI) return;
    refresh();
    unsubscribe = viewerAPI.drawings.onChange(refresh);
  });

  onDestroy(() => unsubscribe?.());

  function selectDrawing(id: string) {
    viewerAPI.drawings.setActive(id);
  }
  function toggleLayer(name: string, visible: boolean) {
    viewerAPI.drawings.toggleActiveLayer(name, visible);
  }
  function setLayerColor(name: string, hex: string) {
    viewerAPI.drawings.setActiveLayerColor(name, Number.parseInt(hex.slice(1), 16));
  }
</script>

<div class="flex h-full flex-col text-xs">
  {#if drawings.length > 1}
    <div class="flex shrink-0 flex-wrap gap-1 border-b border-slate-800 p-2">
      {#each drawings as drawing (drawing.id)}
        <button
          type="button"
          onclick={() => selectDrawing(drawing.id)}
          class="rounded-lg px-2 py-1 {activeDrawingId === drawing.id
            ? 'bg-accent text-white'
            : 'bg-slate-800/60 text-slate-400 hover:text-white'}"
        >
          {drawing.label}
        </button>
      {/each}
    </div>
  {/if}

  {#if activeLayers.length > 0}
    <div class="shrink-0 space-y-0.5 border-b border-slate-800 p-2">
      {#each activeLayers as layer (layer.name)}
        <div class="flex items-center gap-2 rounded-lg px-1 py-1">
          <input
            type="checkbox"
            checked={layer.visible}
            onchange={(e) => toggleLayer(layer.name, (e.target as HTMLInputElement).checked)}
            class="h-3.5 w-3.5 rounded border-slate-600 bg-slate-800 text-accent"
          />
          <input
            type="color"
            value={layer.color}
            onchange={(e) => setLayerColor(layer.name, (e.target as HTMLInputElement).value)}
            class="h-4 w-6 cursor-pointer rounded border-none bg-transparent p-0"
          />
          <span class="truncate text-slate-300">{layer.name}</span>
        </div>
      {/each}
    </div>
  {:else if drawings.length === 0}
    <p class="p-3 text-slate-500">
      No drawings yet — open a plan, elevation, or section view and use "New drawing from current
      view" in the Drawings ribbon tab.
    </p>
  {/if}

  <div bind:this={sheetBoardHost} class="min-h-0 flex-1"></div>
</div>
