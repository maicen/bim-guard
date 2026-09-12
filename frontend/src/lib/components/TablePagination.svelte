<script lang="ts">
  import { Pagination } from "bits-ui";
  import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-svelte";
  import Select, { type SelectOption } from "./ui/Select.svelte";

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

  let pageSizeOptionsMapped: SelectOption[] = $derived(
    pageSizeOptions.map((opt) => ({ value: String(opt), label: String(opt) })),
  );

  function handlePageSizeChange(newVal: string) {
    const parsed = parseInt(newVal, 10);
    if (!isNaN(parsed) && parsed !== pageSize) {
      onPageSizeChange(parsed);
    }
  }

  function goToPage(p: number) {
    const valid = Math.max(1, Math.min(p, totalPages));
    if (valid !== currentPage) {
      onPageChange(valid);
    }
  }
</script>

<Pagination.Root
  count={totalItems}
  perPage={pageSize}
  page={currentPage}
  onPageChange={(p) => {
    if (p !== currentPage) {
      onPageChange(p);
    }
  }}
  siblingCount={1}
>
  {#snippet children({ pages })}
    <div
      class="flex select-none flex-col items-center justify-between gap-4 rounded-b-2xl border-t border-border-subtle bg-surface-canvas/40 px-4 py-3 text-xs text-fg-muted sm:flex-row"
    >
      <!-- Range indicator & Page size selector -->
      <div class="flex flex-wrap items-center gap-4">
        <span>
          Showing <strong class="text-fg-primary">{startItem}</strong> to
          <strong class="text-fg-primary">{endItem}</strong> of
          <strong class="text-fg-primary">{totalItems}</strong> entries
        </span>

        <div class="flex items-center gap-1.5">
          <span>Show</span>
          <div class="w-20">
            <Select
              options={pageSizeOptionsMapped}
              value={String(pageSize)}
              onValueChange={handlePageSizeChange}
              triggerClass="h-7 px-2.5 py-1 text-xs rounded-lg bg-surface-card border-border-default"
              ariaLabel="Entries per page"
            />
          </div>
          <span>per page</span>
        </div>
      </div>

      <!-- Page Navigation Controls -->
      <div class="flex items-center gap-1">
        <!-- First Page -->
        <button
          type="button"
          onclick={() => goToPage(1)}
          disabled={currentPage <= 1}
          class="rounded-lg border border-border-subtle p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary disabled:cursor-not-allowed disabled:opacity-30"
          title="First Page"
          aria-label="First Page"
        >
          <ChevronsLeft class="h-4 w-4" />
        </button>

        <!-- Previous Page -->
        <Pagination.PrevButton
          class="rounded-lg border border-border-subtle p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary disabled:cursor-not-allowed disabled:opacity-30"
          aria-label="Previous Page"
        >
          <ChevronLeft class="h-4 w-4" />
        </Pagination.PrevButton>

        <!-- Page Number Items & Ellipsis -->
        <div class="flex items-center gap-1">
          {#each pages as page (page.key)}
            {#if page.type === "ellipsis"}
              <span class="px-2 py-1 text-xs font-semibold text-fg-muted select-none">…</span>
            {:else}
              <Pagination.Page
                {page}
                class="flex h-7 min-w-7 select-none items-center justify-center rounded-lg border border-border-subtle px-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary data-selected:border-accent data-selected:bg-accent data-selected:text-white"
              >
                {page.value}
              </Pagination.Page>
            {/if}
          {/each}
        </div>

        <!-- Next Page -->
        <Pagination.NextButton
          class="rounded-lg border border-border-subtle p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary disabled:cursor-not-allowed disabled:opacity-30"
          aria-label="Next Page"
        >
          <ChevronRight class="h-4 w-4" />
        </Pagination.NextButton>

        <!-- Last Page -->
        <button
          type="button"
          onclick={() => goToPage(totalPages)}
          disabled={currentPage >= totalPages}
          class="rounded-lg border border-border-subtle p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary disabled:cursor-not-allowed disabled:opacity-30"
          title="Last Page"
          aria-label="Last Page"
        >
          <ChevronsRight class="h-4 w-4" />
        </button>
      </div>
    </div>
  {/snippet}
</Pagination.Root>
