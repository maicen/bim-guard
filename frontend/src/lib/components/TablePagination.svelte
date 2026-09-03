<script lang="ts">
  import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-svelte";

  interface Props {
    currentPage?: number;
    pageSize?: number;
    totalItems?: number;
    pageSizeOptions?: number[];
    onPageChange: (page: number) => void;
    onPageSizeChange: (size: number) => void;
  }

  let {
    currentPage = 1,
    pageSize = 10,
    totalItems = 0,
    pageSizeOptions = [10, 25, 50, 100],
    onPageChange,
    onPageSizeChange,
  }: Props = $props();

  let totalPages = $derived(Math.max(1, Math.ceil(totalItems / pageSize)));
  let startItem = $derived(totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1);
  let endItem = $derived(Math.min(totalItems, currentPage * pageSize));

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
  class="flex select-none flex-col items-center justify-between gap-4 rounded-b-2xl border-t border-slate-800 bg-slate-950/40 px-4 py-3 text-xs text-slate-400 sm:flex-row"
>
  <!-- Range indicator & Page size selector -->
  <div class="flex flex-wrap items-center gap-4">
    <span>
      Showing <strong class="text-slate-200">{startItem}</strong> to
      <strong class="text-slate-200">{endItem}</strong> of
      <strong class="text-slate-200">{totalItems}</strong> entries
    </span>

    <div class="flex items-center gap-1.5">
      <span>Show</span>
      <select
        value={pageSize}
        onchange={handlePageSizeChange}
        class="cursor-pointer rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
      onclick={() => goToPage(1)}
      disabled={currentPage === 1}
      class="rounded-lg border border-slate-800 p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50 disabled:cursor-not-allowed disabled:opacity-30"
      title="First Page"
    >
      <ChevronsLeft class="h-4 w-4" />
    </button>

    <!-- Previous Page -->
    <button
      type="button"
      onclick={() => goToPage(currentPage - 1)}
      disabled={currentPage === 1}
      class="rounded-lg border border-slate-800 p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50 disabled:cursor-not-allowed disabled:opacity-30"
      title="Previous Page"
    >
      <ChevronLeft class="h-4 w-4" />
    </button>

    <!-- Page Indicator -->
    <span class="px-3 py-1 font-semibold text-slate-200">
      Page {currentPage} of {totalPages}
    </span>

    <!-- Next Page -->
    <button
      type="button"
      onclick={() => goToPage(currentPage + 1)}
      disabled={currentPage === totalPages}
      class="rounded-lg border border-slate-800 p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50 disabled:cursor-not-allowed disabled:opacity-30"
      title="Next Page"
    >
      <ChevronRight class="h-4 w-4" />
    </button>

    <!-- Last Page -->
    <button
      type="button"
      onclick={() => goToPage(totalPages)}
      disabled={currentPage === totalPages}
      class="rounded-lg border border-slate-800 p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50 disabled:cursor-not-allowed disabled:opacity-30"
      title="Last Page"
    >
      <ChevronsRight class="h-4 w-4" />
    </button>
  </div>
</div>
