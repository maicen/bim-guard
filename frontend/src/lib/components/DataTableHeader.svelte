<script lang="ts">
  import { Search, RotateCw, RotateCcw, X } from "lucide-svelte";

  interface Props {
    searchQuery?: string;
    searchPlaceholder?: string;
    selectedCount?: number;
    selectedLabel?: string;
    onClearSelection?: (() => void) | null;
    hasActiveFilters?: boolean;
    onResetFilters?: (() => void) | null;
    isRefreshing?: boolean;
    onRefresh?: (() => void) | null;
    customClass?: string;
    filters?: import("svelte").Snippet;
    actions?: import("svelte").Snippet;
  }

  let {
    searchQuery = $bindable(""),
    searchPlaceholder = "Search items...",
    selectedCount = 0,
    selectedLabel = "item",
    onClearSelection = null,
    hasActiveFilters = false,
    onResetFilters = null,
    isRefreshing = false,
    onRefresh = null,
    customClass = "",
    filters,
    actions,
  }: Props = $props();
</script>

<div
  class="flex flex-col justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 md:flex-row md:items-center {customClass}"
>
  <!-- Search & Filter Controls -->
  <div class="flex flex-1 flex-wrap items-center gap-3">
    <!-- Search Input Bar -->
    <div class="relative min-w-[14rem] max-w-md flex-1">
      <Search
        class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
      />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder={searchPlaceholder}
        class="w-full rounded-xl border border-slate-700 bg-slate-950 py-2 pl-9 pr-8 text-xs text-slate-200 placeholder-slate-500 transition-colors focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
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

    <!-- Filters Slot -->
    {@render filters?.()}

    <!-- Reset Active Filters Button -->
    {#if hasActiveFilters && onResetFilters}
      <button
        type="button"
        onclick={onResetFilters}
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
        title="Reset all filters"
      >
        <RotateCcw class="h-3.5 w-3.5" />
        <span>Reset</span>
      </button>
    {/if}
  </div>

  <!-- Selection summary, Refresh, and Actions Slot -->
  <div class="flex flex-wrap items-center gap-3">
    {#if selectedCount > 0}
      <div class="flex items-center gap-2 text-xs text-violet-300">
        <span>
          <strong class="font-bold text-violet-200">{selectedCount}</strong>
          {selectedLabel}{selectedCount === 1 ? "" : "s"} selected
        </span>
        {#if onClearSelection}
          <button
            type="button"
            onclick={onClearSelection}
            class="text-micro underline text-slate-400 hover:text-slate-200"
          >
            Clear
          </button>
        {/if}
      </div>
    {/if}

    {#if onRefresh}
      <button
        type="button"
        onclick={onRefresh}
        disabled={isRefreshing}
        class="rounded-xl border border-slate-700 bg-slate-800 p-2 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-50 disabled:opacity-50"
        title="Refresh data"
      >
        <RotateCw class="h-4 w-4 {isRefreshing ? 'animate-spin' : ''}" />
      </button>
    {/if}

    {@render actions?.()}
  </div>
</div>
