import { SvelteSet } from "svelte/reactivity";

/**
 * Search / filter / sort / paginate / select state for a data table.
 *
 * Eight route files each re-implemented these four concerns, and they had
 * already drifted: two views sorted the same column differently because one
 * comparator lowercased and null-coalesced and the other did not, and the
 * "reset to page 1 when the filter changes" step was manual, so forgetting it
 * stranded the user on an empty page. This owns all of it once.
 *
 *     const table = createTableState({
 *       rows: () => projects,
 *       getId: (p) => p.id,
 *       searchFields: (p) => [p.name, p.country],
 *       filters: { status: (p, v) => p.status === v },
 *       initialSort: { field: "created_at", asc: false },
 *     });
 *
 * `rows` is a getter, not an array, so the state tracks whatever reactive
 * source the caller passes.
 */

export type SortDirection = "asc" | "desc";

export type RowId = string | number;

export interface TableStateOptions<T, Id extends RowId = RowId> {
  /** Getter for the full row set; called inside a $derived so it stays live. */
  rows: () => T[];
  /** Stable identity for selection. */
  getId: (row: T) => Id;
  /** Values the free-text search matches against. */
  searchFields?: (row: T) => (string | null | undefined)[];
  /**
   * Named predicates. A filter is skipped while its value is unset or "all",
   * which is the convention every existing view already uses.
   */
  filters?: Record<string, (row: T, value: string) => boolean>;
  /** Per-field comparators for columns that do not sort as plain strings. */
  comparators?: Record<string, (a: T, b: T) => number>;
  initialSort?: { field: string; asc?: boolean };
  initialPageSize?: number;
}

/** Case-insensitive, null-safe comparison — the correct one of the two that had drifted. */
function defaultCompare(a: unknown, b: unknown): number {
  let x: any = a ?? "";
  let y: any = b ?? "";
  if (typeof x === "string") x = x.toLowerCase();
  if (typeof y === "string") y = y.toLowerCase();
  if (x < y) return -1;
  if (x > y) return 1;
  return 0;
}

export class TableState<T, Id extends RowId = RowId> {
  #options: TableStateOptions<T, Id>;

  search = $state("");
  filters = $state<Record<string, string>>({});
  sortField = $state<string>("");
  sortAsc = $state(true);
  pageSize = $state(10);
  /** Requested page. Read `page` for the clamped, always-valid value. */
  requestedPage = $state(1);
  selectedIds = new SvelteSet<Id>();

  constructor(options: TableStateOptions<T, Id>) {
    this.#options = options;
    this.sortField = options.initialSort?.field ?? "";
    this.sortAsc = options.initialSort?.asc ?? true;
    this.pageSize = options.initialPageSize ?? 10;
  }

  filtered = $derived.by(() => {
    const { rows, searchFields, filters } = this.#options;
    const needle = this.search.trim().toLowerCase();

    return rows().filter((row) => {
      if (needle && searchFields) {
        const hit = searchFields(row).some((field) =>
          (field ?? "").toString().toLowerCase().includes(needle),
        );
        if (!hit) return false;
      }
      if (filters) {
        for (const [key, predicate] of Object.entries(filters)) {
          const value = this.filters[key];
          // Empty or "all" means the filter is off. Case-insensitive because
          // the views spell the sentinel both "all" and "ALL".
          if (!value || value.toLowerCase() === "all") continue;
          if (!predicate(row, value)) return false;
        }
      }
      return true;
    });
  });

  sorted = $derived.by(() => {
    const field = this.sortField;
    if (!field) return this.filtered;
    const custom = this.#options.comparators?.[field];
    const direction = this.sortAsc ? 1 : -1;
    // Copy first: sorting `filtered` in place would mutate a derived value.
    return [...this.filtered].sort(
      (a, b) =>
        direction * (custom ? custom(a, b) : defaultCompare((a as any)[field], (b as any)[field])),
    );
  });

  totalItems = $derived(this.filtered.length);
  totalPages = $derived(Math.max(1, Math.ceil(this.totalItems / this.pageSize)));

  /**
   * The page actually shown. Clamping rather than resetting means narrowing a
   * filter can never strand the user on an empty page, without any view having
   * to remember to reset.
   */
  page = $derived(Math.min(Math.max(1, this.requestedPage), this.totalPages));

  paginated = $derived(
    this.sorted.slice((this.page - 1) * this.pageSize, this.page * this.pageSize),
  );

  // --- selection ----------------------------------------------------------

  selectedCount = $derived(this.selectedIds.size);

  /** Selected ids as an array, for components that take a plain list prop. */
  selectedIdList = $derived([...this.selectedIds]);

  /** Ids of the currently filtered rows, i.e. what "select all" acts on. */
  #filteredIds = $derived(this.filtered.map((row) => this.#options.getId(row)));

  allFilteredSelected = $derived(
    this.#filteredIds.length > 0 && this.#filteredIds.every((id) => this.selectedIds.has(id)),
  );

  someFilteredSelected = $derived(
    !this.allFilteredSelected && this.#filteredIds.some((id) => this.selectedIds.has(id)),
  );

  isSelected(id: Id): boolean {
    return this.selectedIds.has(id);
  }

  toggleSelect(id: Id) {
    if (this.selectedIds.has(id)) this.selectedIds.delete(id);
    else this.selectedIds.add(id);
  }

  toggleSelectAll() {
    if (this.allFilteredSelected) {
      for (const id of this.#filteredIds) this.selectedIds.delete(id);
    } else {
      for (const id of this.#filteredIds) this.selectedIds.add(id);
    }
  }

  clearSelection() {
    this.selectedIds.clear();
  }

  /** The selected rows, in the current sort order. */
  selectedRows = $derived(
    this.sorted.filter((row) => this.selectedIds.has(this.#options.getId(row))),
  );

  // --- sorting / paging ---------------------------------------------------

  toggleSort(field: string) {
    if (this.sortField === field) {
      this.sortAsc = !this.sortAsc;
    } else {
      this.sortField = field;
      this.sortAsc = true;
    }
  }

  sortDirection(field: string): SortDirection | null {
    if (this.sortField !== field) return null;
    return this.sortAsc ? "asc" : "desc";
  }

  setFilter(key: string, value: string) {
    this.filters = { ...this.filters, [key]: value };
  }

  /** Clear search and every filter. */
  reset() {
    this.search = "";
    this.filters = {};
    this.requestedPage = 1;
  }

  get hasActiveFilters(): boolean {
    return (
      this.search.trim() !== "" ||
      Object.values(this.filters).some((v) => v && v.toLowerCase() !== "all")
    );
  }
}

export function createTableState<T, Id extends RowId = RowId>(
  options: TableStateOptions<T, Id>,
): TableState<T, Id> {
  return new TableState(options);
}
