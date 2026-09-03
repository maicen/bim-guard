<script lang="ts">
  import type { ComponentType } from "svelte";
  import { SearchX } from "lucide-svelte";

  export let title: string = "No items found";
  export let description: string = "";
  export let icon: ComponentType | null = null;
  export let actionLabel: string = "";
  export let onAction: (() => void) | null = null;
</script>

<div
  class="p-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl space-y-3 animate-in fade-in duration-200"
>
  <div
    class="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-slate-400"
  >
    {#if icon}
      <svelte:component this={icon} class="w-6 h-6" />
    {:else}
      <SearchX class="w-6 h-6 text-slate-500" />
    {/if}
  </div>

  <div class="space-y-1">
    <div class="text-sm font-bold text-slate-50">{title}</div>
    {#if description}
      <div class="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
        {description}
      </div>
    {/if}
  </div>

  <slot />

  {#if actionLabel && onAction}
    <div class="pt-1">
      <button
        type="button"
        on:click={onAction}
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-accent hover:bg-accent-hover text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
      >
        <span>{actionLabel}</span>
      </button>
    </div>
  {/if}
</div>
