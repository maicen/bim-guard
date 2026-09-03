<script lang="ts">
  import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-svelte";

  export let column: string;
  export let sortField: string;
  export let sortAsc: boolean = true;
  export let onSort: (col: any) => void;
  export let align: "left" | "center" | "right" = "left";
  export let customClass: string = "py-3 px-4";
</script>

<th
  class="{customClass} cursor-pointer hover:text-slate-50 transition-colors select-none group text-caption uppercase tracking-wider text-slate-400 font-semibold"
  on:click={() => onSort(column)}
  role="columnheader"
  aria-sort={sortField === column ? (sortAsc ? "ascending" : "descending") : "none"}
>
  <div
    class="flex items-center gap-1 {align === 'center' ? 'justify-center' : align === 'right' ? 'justify-end' : 'justify-start'}"
  >
    <span><slot /></span>
    {#if sortField === column}
      {#if sortAsc}
        <ArrowUp class="w-3 h-3 text-accent shrink-0" />
      {:else}
        <ArrowDown class="w-3 h-3 text-accent shrink-0" />
      {/if}
    {:else}
      <ArrowUpDown class="w-3 h-3 text-slate-600 group-hover:text-slate-400 transition-colors shrink-0" />
    {/if}
  </div>
</th>
