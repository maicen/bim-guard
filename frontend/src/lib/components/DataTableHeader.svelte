<script lang="ts">
  import { Search, RotateCw, X } from "lucide-svelte";

  export let searchQuery: string = "";
  export let searchPlaceholder: string = "Search items...";
  export let isRefreshing: boolean = false;
  export let onRefresh: (() => void) | null = null;
</script>

<div
  class="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 rounded-t-2xl bg-slate-900/60 border border-slate-800 border-b-0"
>
  <!-- Search Input Bar -->
  <div class="relative flex-1 min-w-[14rem] max-w-md">
    <Search
      class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
    />
    <input
      type="text"
      bind:value={searchQuery}
      placeholder={searchPlaceholder}
      class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-8 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
    />
    {#if searchQuery}
      <button
        type="button"
        on:click={() => (searchQuery = "")}
        class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-50 p-0.5"
        title="Clear search"
      >
        <X class="w-3.5 h-3.5" />
      </button>
    {/if}
  </div>

  <!-- Filters & Primary CTA slot -->
  <div class="flex items-center gap-2.5 flex-wrap">
    <slot name="filters" />

    {#if onRefresh}
      <button
        type="button"
        on:click={onRefresh}
        disabled={isRefreshing}
        class="p-2 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-400 hover:text-slate-50 disabled:opacity-50 transition-colors"
        title="Refresh data"
      >
        <RotateCw class="w-4 h-4 {isRefreshing ? 'animate-spin' : ''}" />
      </button>
    {/if}

    <slot name="actions" />
  </div>
</div>
