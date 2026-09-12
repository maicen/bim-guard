<script lang="ts">
  import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-svelte";

  interface Props {
    column: string;
    sortField: string;
    sortAsc?: boolean;
    onSort: (col: any) => void;
    align?: "left" | "center" | "right";
    customClass?: string;
    children?: import("svelte").Snippet;
  }

  let {
    column,
    sortField,
    sortAsc = true,
    onSort,
    align = "left",
    customClass = "py-3 px-4",
    children,
  }: Props = $props();
</script>

<th
  class="{customClass} group cursor-pointer select-none text-caption font-semibold uppercase tracking-wider text-fg-muted transition-colors hover:text-fg-primary"
  onclick={() => onSort(column)}
  role="columnheader"
  aria-sort={sortField === column ? (sortAsc ? "ascending" : "descending") : "none"}
>
  <div
    class="flex items-center gap-1 {align === 'center'
      ? 'justify-center'
      : align === 'right'
        ? 'justify-end'
        : 'justify-start'}"
  >
    <span>{@render children?.()}</span>
    {#if sortField === column}
      {#if sortAsc}
        <ArrowUp class="h-3 w-3 shrink-0 text-accent" />
      {:else}
        <ArrowDown class="h-3 w-3 shrink-0 text-accent" />
      {/if}
    {:else}
      <ArrowUpDown
        class="h-3 w-3 shrink-0 text-fg-muted transition-colors group-hover:text-fg-secondary"
      />
    {/if}
  </div>
</th>
