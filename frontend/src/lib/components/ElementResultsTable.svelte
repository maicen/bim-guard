<script lang="ts">
  import { AlertTriangle, Search } from "lucide-svelte";
  import SortHeader from "./SortHeader.svelte";
  import TablePagination from "./TablePagination.svelte";
  import ConfidenceMeter from "./ConfidenceMeter.svelte";
  import Tooltip from "./Tooltip.svelte";
  import { UNKNOWN_PROPERTY_CONFIDENCE } from "../propertyConfidence";
  import type { RuleElementResult } from "../types";
  import { splitRoomLabel } from "../roomTypes";

  interface Props {
    elements: RuleElementResult[];
    unit?: string;
    requiredText: string;
    fmtVal: (v: any) => string;
    onViewIn3d?: (guid: string) => void;
  }

  let { elements, unit = "", requiredText, fmtVal, onViewIn3d }: Props = $props();

  let search = $state("");
  // Defaults to the most accurate property resolution first — a value read
  // straight off the element's own Pset ranks above a geometry-bbox guess,
  // regardless of whether the rule passed or failed.
  let sortField = $state("confidence");
  let sortAsc = $state(true);
  let currentPage = $state(1);
  let pageSize = $state(25);

  function confidenceRank(el: RuleElementResult): number {
    return (el.property_confidence ?? UNKNOWN_PROPERTY_CONFIDENCE).rank;
  }

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
            (el.guid || "").toLowerCase().includes(q) ||
            (el.connected_room_labels || []).some((r) => r.toLowerCase().includes(q)) ||
            (el.connected_room_ids || []).some((r) => r.toLowerCase().includes(q))
          );
        })
      : elements,
  );

  let sorted = $derived(
    [...filtered].sort((a, b) => {
      let cmp: number;
      if (sortField === "confidence") {
        cmp = confidenceRank(a) - confidenceRank(b);
      } else if (sortField === "status") {
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
  let showsRoomIds = $derived(elements.some((el) => el.connected_room_labels?.length));

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

<div class="border-t border-border-subtle">
  <div class="flex items-center gap-2 border-b border-border-subtle px-3.5 py-2">
    <Search class="h-3.5 w-3.5 shrink-0 text-fg-muted" />
    <input
      type="text"
      bind:value={search}
      placeholder="Filter by element, floor, room, room ID, or GUID…"
      class="w-full bg-transparent text-xs text-fg-secondary placeholder:text-fg-muted focus:outline-hidden"
    />
  </div>
  <div class="max-h-64 overflow-auto">
    <table aria-label="Element compliance results" class="w-full text-xs">
      <thead>
        <tr class="bg-surface-overlay">
          <SortHeader column="element" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Element</SortHeader
          >
          <SortHeader column="location" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Floor / Room</SortHeader
          >
          <th scope="col" class="px-3 py-2 text-left text-xs font-semibold text-fg-muted">GUID</th>
          <SortHeader column="actual" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Actual</SortHeader
          >
          <th scope="col" class="px-3 py-2 text-left text-xs font-semibold text-fg-muted">Required</th>
          <SortHeader column="status" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Status</SortHeader
          >
          <SortHeader column="confidence" {sortField} {sortAsc} {onSort} customClass="px-3 py-2"
            >Confidence</SortHeader
          >
        </tr>
      </thead>
      <tbody>
        {#each paged as el (el.guid)}
          {@const fullName = el.element_name || "—"}
          <tr class="border-b border-border-subtle last:border-0 {rowBg(el)}">
            <td class="max-w-xs px-3 py-2">
              <span class="inline-flex items-start gap-1">
                {#if el.data_quality_warnings?.length}
                  <Tooltip text={el.data_quality_warnings.join(" ")}>
                    {#snippet trigger()}
                      <AlertTriangle class="mt-0.5 h-3 w-3 shrink-0 text-amber-400" />
                    {/snippet}
                  </Tooltip>
                {/if}
                <span class="wrap-break-word min-w-0 font-mono text-xs text-fg-primary">{fullName}</span>
              </span>
            </td>
            <td class="px-3 py-2">
              <span class="block text-xs text-fg-secondary">{el.storey || "—"}</span>
              {#if el.space && el.space !== "—"}
                <span class="block text-xs text-fg-muted">{el.space}</span>
              {/if}
              {#each el.connected_room_labels ?? [] as label (label)}
                {@const room = splitRoomLabel(label)}
                <span class="block text-xs text-fg-muted"
                  >{room.name}
                  {#if room.id}<span class="font-mono text-nano text-fg-muted">{room.id}</span>{/if}</span
                >
              {/each}
            </td>
            <td class="px-3 py-2"
              ><!-- The tail, not the head: one export's IFC GUIDs share a long
                   prefix, so the first characters read identical across rows. -->
              {#if el.guid}
                <Tooltip text={el.guid}>
                  {#snippet trigger()}
                    <span class="font-mono text-xs text-fg-muted"
                      >{el.guid!.length > 12 ? `…${el.guid!.slice(-12)}` : el.guid}</span
                    >
                  {/snippet}
                </Tooltip>
              {/if}</td
            >
            <td class="px-3 py-2 font-mono text-xs text-fg-secondary {statusClass(el)}">{actualText(el)}</td>
            <td class="px-3 py-2 text-xs text-fg-muted">{requiredText}</td>
            <td class="px-3 py-2 text-xs {statusClass(el)}">
              {statusLabel(el)}
              {#if el.status === "MISSING" && el.reason && el.reason !== "property not found"}
                <span class="mt-0.5 block max-w-xs font-normal text-fg-muted">{el.reason}</span>
              {/if}
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
            <td class="px-3 py-2">
              <ConfidenceMeter confidence={el.property_confidence} />
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="7" class="px-3 py-6 text-center text-xs italic text-fg-muted">
              No elements match "{search}".
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if showsRoomIds}
    <p class="border-t border-border-subtle px-3.5 py-1.5 text-micro text-fg-muted">
      A room's <span class="font-mono">[#id]</span> is the end of its IFC GlobalId. It tells rooms with
      the same name apart, so you can find the exact room in your model.
    </p>
  {/if}
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
