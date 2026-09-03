<script lang="ts">
  import { Search, RotateCw, X } from "lucide-svelte";

  interface Props {
    searchQuery?: string;
    searchPlaceholder?: string;
    isRefreshing?: boolean;
    onRefresh?: (() => void) | null;
    filters?: import("svelte").Snippet;
    actions?: import("svelte").Snippet;
  }

  let {
    searchQuery = $bindable(""),
    searchPlaceholder = "Search items...",
    isRefreshing = false,
    onRefresh = null,
    filters,
    actions,
  }: Props = $props();
</script>

<div
  class="flex flex-col justify-between gap-3 rounded-t-2xl border border-b-0 border-slate-800 bg-slate-900/60 p-4 md:flex-row md:items-center"
>
  <!-- Search Input Bar -->
  <div class="relative min-w-[14rem] max-w-md flex-1">
    <Search
      class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
    />
    <input
      type="text"
      bind:value={searchQuery}
      placeholder={searchPlaceholder}
      class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-9 pr-8 text-xs text-slate-50 placeholder-slate-500 transition-colors focus:border-blue-500 focus:outline-none"
    />
    {#if searchQuery}
      <button
        type="button"
        onclick={() => (searchQuery = "")}
        class="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-slate-50"
        title="Clear search"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    {/if}
  </div>

  <!-- Filters & Primary CTA slot -->
  <div class="flex flex-wrap items-center gap-2.5">
    {@render filters?.()}

    {#if onRefresh}
      <button
        type="button"
        onclick={onRefresh}
        disabled={isRefreshing}
        class="rounded-xl border border-slate-800 bg-slate-950 p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50 disabled:opacity-50"
        title="Refresh data"
      >
        <RotateCw class="h-4 w-4 {isRefreshing ? 'animate-spin' : ''}" />
      </button>
    {/if}

    {@render actions?.()}
  </div>
</div>
