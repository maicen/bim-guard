<script lang="ts">
  import { AlertTriangle, Search } from "lucide-svelte";
  import SortHeader from "./SortHeader.svelte";
  import TablePagination from "./TablePagination.svelte";
  import type { RuleElementResult } from "../types";

  interface Props {
    elements: RuleElementResult[];
    unit?: string;
    requiredText: string;
    fmtVal: (v: any) => string;
    onViewIn3d?: (guid: string) => void;
  }

  let { elements, unit = "", requiredText, fmtVal, onViewIn3d }: Props = $props();

  let search = $state("");
  let sortField = $state("status");
  let sortAsc = $state(true);
  let currentPage = $state(1);
  let pageSize = $state(25);

  const STATUS_ORDER: Record<string, number> = { FAIL: 0, MISSING: 1, PASS: 2 };

  function statusLabel(el: RuleElementResult): string {
    const s = el.status || "";
    if (s === "FAIL") return el.reason || "fail";
    if (s === "MISSING") return "missing";
    return "✓ pass";
  }

  function statusClass(el: RuleElementResult): string {
    const s = el.status || "";
    if (s === "FAIL") return "text-rose-400 font-semibold";
    if (s === "MISSING") return "text-amber-400 font-semibold";
    return "text-emerald-400";
  }

  function rowBg(el: RuleElementResult): string {
    const s = el.status || "";
    if (s === "FAIL") return "bg-rose-950/20";
    if (s === "MISSING") return "bg-amber-950/20";
    return "";
  }

  function actualText(el: RuleElementResult): string {
    return fmtVal(el.actual) + (unit && el.actual != null ? ` ${unit}` : "");
  }

  let filtered = $derived(
    search.trim()
      ? elements.filter((el) => {
          const q = search.trim().toLowerCase();
          return (
            (el.element_name || "").toLowerCase().includes(q) ||
            (el.storey || "").toLowerCase().includes(q) ||
            (el.space || "").toLowerCase().includes(q) ||
            (el.guid || "").toLowerCase().includes(q)
          );
        })
      : elements,
  );

  let sorted = $derived(
    [...filtered].sort((a, b) => {
      let cmp: number;
      if (sortField === "status") {
        cmp = (STATUS_ORDER[a.status ?? ""] ?? 3) - (STATUS_ORDER[b.status ?? ""] ?? 3);
      } else if (sortField === "actual") {
        cmp = actualText(a).localeCompare(actualText(b));
      } else if (sortField === "location") {
        cmp = (a.storey || "").localeCompare(b.storey || "");
      } else {
        cmp = (a.element_name || "").localeCompare(b.element_name || "");
      }
      return sortAsc ? cmp : -cmp;
    }),
  );

  let paged = $derived(sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize));

  function onSort(col: string) {
    if (sortField === col) {
      sortAsc = !sortAsc;
    } else {
      sortField = col;
      sortAsc = true;
    }
    currentPage = 1;
  }

  $effect(() => {
    // Reset to page 1 whenever the search narrows the result set.
    void search;
    currentPage = 1;
  });
</script>

<div class="border-t border-slate-800/60">
  <div class="flex items-center gap-2 border-b border-slate-800/60 px-3.5 py-2">
    <Search class="h-3.5 w-3.5 shrink-0 text-slate-500" />
    <input
      type="text"
      bind:value={search}
      placeholder="Filter by element, floor, room, or GUID…"
      class="w-full bg-transparent text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none"
    />
  </div>
  <div class="max-h-64 overflow-auto">
    <table class="w-full text-xs">
      <thead>
        <tr class="bg-slate-800/80">
          <SortHeader column="element" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Element</SortHeader
          >
          <SortHeader column="location" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Floor / Room</SortHeader
          >
          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">GUID</th>
          <SortHeader column="actual" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Actual</SortHeader
          >
          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Required</th>
          <SortHeader column="status" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Status</SortHeader
          >
        </tr>
      </thead>
      <tbody>
        {#each paged as el (el.guid)}
          <tr class="border-b border-slate-800/40 last:border-0 {rowBg(el)}">
            <td class="px-3 py-2">
              <span class="inline-flex items-center gap-1">
                {#if el.data_quality_warnings?.length}
                  <span title={el.data_quality_warnings.join(" ")}>
                    <AlertTriangle class="h-3 w-3 shrink-0 text-amber-400" />
                  </span>
                {/if}
                <span class="font-mono text-xs text-slate-50">{(el.element_name || "—").slice(0, 32)}</span>
              </span>
            </td>
            <td class="px-3 py-2">
              <span class="block text-xs text-slate-300">{el.storey || "—"}</span>
              {#if el.space && el.space !== "—"}
                <span class="block text-xs text-slate-500">{el.space}</span>
              {/if}
            </td>
            <td class="px-3 py-2"
              ><span class="font-mono text-xs text-slate-500">{(el.guid || "").slice(0, 14)}</span></td
            >
            <td class="px-3 py-2 font-mono text-xs text-slate-300 {statusClass(el)}">{actualText(el)}</td>
            <td class="px-3 py-2 text-xs text-slate-500">{requiredText}</td>
            <td class="px-3 py-2 text-xs {statusClass(el)}">
              {statusLabel(el)}
              {#if el.status === "FAIL" && el.guid && onViewIn3d}
                <button
                  type="button"
                  class="ml-2 text-blue-400 hover:text-blue-300 hover:underline"
                  onclick={(e) => {
                    e.stopPropagation();
                    onViewIn3d?.(el.guid!);
                  }}>View in 3D</button
                >
              {/if}
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="6" class="px-3 py-6 text-center text-xs italic text-slate-500">
              No elements match "{search}".
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <TablePagination
    {currentPage}
    {pageSize}
    totalItems={sorted.length}
    pageSizeOptions={[10, 25, 50, 100]}
    onPageChange={(p) => (currentPage = p)}
    onPageSizeChange={(s) => {
      pageSize = s;
      currentPage = 1;
    }}
  />
</div>
