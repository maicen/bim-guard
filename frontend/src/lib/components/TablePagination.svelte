<script lang="ts">
  import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-svelte";

  export let currentPage: number = 1;
  export let pageSize: number = 10;
  export let totalItems: number = 0;
  export let pageSizeOptions: number[] = [10, 25, 50, 100];
  export let onPageChange: (page: number) => void;
  export let onPageSizeChange: (size: number) => void;

  $: totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  $: startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  $: endItem = Math.min(totalItems, currentPage * pageSize);

  function goToPage(page: number) {
    const validPage = Math.max(1, Math.min(page, totalPages));
    if (validPage !== currentPage) {
      onPageChange(validPage);
    }
  }

  function handlePageSizeChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    const newSize = parseInt(target.value, 10);
    onPageSizeChange(newSize);
  }
</script>

<div
  class="flex flex-col sm:flex-row items-center justify-between gap-4 py-3 px-4 border-t border-slate-800 bg-slate-950/40 text-xs text-slate-400 select-none rounded-b-2xl"
>
  <!-- Range indicator & Page size selector -->
  <div class="flex items-center gap-4 flex-wrap">
    <span>
      Showing <strong class="text-slate-200">{startItem}</strong> to
      <strong class="text-slate-200">{endItem}</strong> of
      <strong class="text-slate-200">{totalItems}</strong> entries
    </span>

    <div class="flex items-center gap-1.5">
      <span>Show</span>
      <select
        value={pageSize}
        on:change={handlePageSizeChange}
        class="bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
      >
        {#each pageSizeOptions as option}
          <option value={option}>{option}</option>
        {/each}
      </select>
      <span>per page</span>
    </div>
  </div>

  <!-- Page Navigation Controls -->
  <div class="flex items-center gap-1">
    <!-- First Page -->
    <button
      type="button"
      on:click={() => goToPage(1)}
      disabled={currentPage === 1}
      class="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      title="First Page"
    >
      <ChevronsLeft class="w-4 h-4" />
    </button>

    <!-- Previous Page -->
    <button
      type="button"
      on:click={() => goToPage(currentPage - 1)}
      disabled={currentPage === 1}
      class="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      title="Previous Page"
    >
      <ChevronLeft class="w-4 h-4" />
    </button>

    <!-- Page Indicator -->
    <span class="px-3 py-1 font-semibold text-slate-200">
      Page {currentPage} of {totalPages}
    </span>

    <!-- Next Page -->
    <button
      type="button"
      on:click={() => goToPage(currentPage + 1)}
      disabled={currentPage === totalPages}
      class="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      title="Next Page"
    >
      <ChevronRight class="w-4 h-4" />
    </button>

    <!-- Last Page -->
    <button
      type="button"
      on:click={() => goToPage(totalPages)}
      disabled={currentPage === totalPages}
      class="p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      title="Last Page"
    >
      <ChevronsRight class="w-4 h-4" />
    </button>
  </div>
</div>
