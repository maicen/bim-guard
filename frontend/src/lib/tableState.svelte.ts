import { SvelteSet, SvelteMap } from "svelte/reactivity";
import { toasts } from "./toast.svelte";

/**
 * Search / filter / sort / paginate / select / optimistic state for a data table.
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

export interface OptimisticDeleteOptions<Id, R = unknown> {
  /** Target row ID or array of IDs to optimistically remove */
  ids: Id | Id[];
  /** Server action promise to perform */
  action: () => Promise<R>;
  /** Callback called immediately after server succeeds */
  onSuccess?: (result: R) => void;
  /** Callback called if server action fails (defaults to toast notification) */
  onError?: (error: any) => void;
  /** Optional rollback hook */
  rollback?: () => void;
}

export interface OptimisticUpdateOptions<T, Id, R = unknown> {
  /** Target row ID or array of IDs to optimistically patch */
  ids: Id | Id[];
  /** Patch object or callback returning patch per row */
  patch: Partial<T> | ((row: T) => Partial<T>);
  /** Server action promise to perform */
  action: () => Promise<R>;
  /** Callback called immediately after server succeeds */
  onSuccess?: (result: R) => void;
  /** Callback called if server action fails (defaults to toast notification) */
  onError?: (error: any) => void;
  /** Optional rollback hook */
  rollback?: () => void;
}

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

  /** Optimistically pending deletions (hidden from table derived views). */
  pendingDeletions = new SvelteSet<Id>();

  /** Optimistically pending updates/patches (merged into table derived views). */
  pendingUpdates = new SvelteMap<Id, Partial<T>>();

  constructor(options: TableStateOptions<T, Id>) {
    this.#options = options;
    this.sortField = options.initialSort?.field ?? "";
    this.sortAsc = options.initialSort?.asc ?? true;
    this.pageSize = options.initialPageSize ?? 10;
    this.filters = this.#defaultFilters();
  }

  /**
   * "ALL" for every declared filter key -- the sentinel every view already
   * uses to mean "this filter is off" (see `filtered` below and
   * `hasActiveFilters`). Every caller that renders a filter as
   * `<Select bind:value={table.filters.key}>` needs that key to be defined
   * from the very first render: a `bind:` target that reads as `undefined`
   * while the bindable prop on the other end (`Select`'s
   * `value = $bindable("")`) has a fallback throws `props_invalid_value` --
   * Svelte cannot tell "nothing was passed, use the fallback" apart from
   * "this is two-way bound to a real value that happens to be undefined
   * right now", so it refuses to guess and throws instead. Starting from
   * `{}` left every key undefined until the user touched that dropdown at
   * least once, which crashed the whole view on mount.
   */
  #defaultFilters(): Record<string, string> {
    return Object.fromEntries(Object.keys(this.#options.filters ?? {}).map((key) => [key, "ALL"]));
  }

  filtered = $derived.by(() => {
    const { rows, searchFields, filters } = this.#options;
    const needle = this.search.trim().toLowerCase();

    // 1. Exclude rows optimistically marked for deletion
    // 2. Overlay any optimistic in-flight field patches
    const activeRows = rows()
      .filter((row) => !this.pendingDeletions.has(this.#options.getId(row)))
      .map((row) => {
        const patch = this.pendingUpdates.get(this.#options.getId(row));
        return patch ? { ...row, ...patch } : row;
      });

    return activeRows.filter((row) => {
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
    this.filters = this.#defaultFilters();
    this.requestedPage = 1;
  }

  get hasActiveFilters(): boolean {
    return (
      this.search.trim() !== "" ||
      Object.values(this.filters).some((v) => v && v.toLowerCase() !== "all")
    );
  }

  // --- optimistic mutation & status helpers ---------------------------------

  /** Returns true if the row has any in-flight optimistic operation (deletion or update). */
  isPending(id: Id): boolean {
    return this.pendingDeletions.has(id) || this.pendingUpdates.has(id);
  }

  /** Returns true if the row is currently undergoing optimistic deletion. */
  isPendingDeletion(id: Id): boolean {
    return this.pendingDeletions.has(id);
  }

  /** Returns true if the row has an active optimistic patch applied. */
  isPendingUpdate(id: Id): boolean {
    return this.pendingUpdates.has(id);
  }

  /** Returns the active optimistic patch for the specified row, if any. */
  getPendingUpdate(id: Id): Partial<T> | undefined {
    return this.pendingUpdates.get(id);
  }

  /** Helper to generate accessible optimistic pending CSS classes for table rows. */
  rowClass(id: Id, baseClass = ""): string {
    const isPending = this.isPending(id);
    if (!isPending) return baseClass;
    return baseClass
      ? `${baseClass} opacity-50 pointer-events-none transition-opacity duration-200`
      : "opacity-50 pointer-events-none transition-opacity duration-200";
  }

  /**
   * Perform an optimistic deletion on one or multiple rows.
   *
   * 1. Instantly removes the rows from selection and table derived views (`filtered`, `sorted`, `paginated`).
   * 2. Executes the server action promise.
   * 3. On success: calls `onSuccess`, cleans up pending state, and returns `{ success: true, result }`.
   * 4. On failure: rolls back row visibility, restores previous selection, calls `rollback` and `onError`,
   *    and returns `{ success: false, error }`.
   */
  async optimisticDelete<R = unknown>(
    options: OptimisticDeleteOptions<Id, R>,
  ): Promise<{ success: boolean; result?: R; error?: any }> {
    const targetIds = Array.isArray(options.ids) ? options.ids : [options.ids];
    if (targetIds.length === 0) return { success: true };

    // Remember which rows were selected so selection can be restored on failure
    const selectedToRestore = targetIds.filter((id) => this.selectedIds.has(id));

    // Optimistically hide rows and remove from selection
    for (const id of targetIds) {
      this.selectedIds.delete(id);
      this.pendingDeletions.add(id);
    }

    try {
      const result = await options.action();
      options.onSuccess?.(result);
      for (const id of targetIds) {
        this.pendingDeletions.delete(id);
      }
      return { success: true, result };
    } catch (err: any) {
      // Roll back
      for (const id of targetIds) {
        this.pendingDeletions.delete(id);
      }
      for (const id of selectedToRestore) {
        this.selectedIds.add(id);
      }
      options.rollback?.();
      if (options.onError) {
        options.onError(err);
      } else {
        toasts.fromError(err, "Failed to complete deletion. Changes were reverted.");
      }
      return { success: false, error: err };
    }
  }

  /**
   * Perform an optimistic update/patch on one or multiple rows.
   *
   * 1. Instantly applies `patch` to the target rows in all derived views.
   * 2. Executes the server action promise.
   * 3. On success: calls `onSuccess`, cleans up pending patch, and returns `{ success: true, result }`.
   * 4. On failure: rolls back patches, calls `rollback` and `onError`, and returns `{ success: false, error }`.
   */
  async optimisticUpdate<R = unknown>(
    options: OptimisticUpdateOptions<T, Id, R>,
  ): Promise<{ success: boolean; result?: R; error?: any }> {
    const targetIds = Array.isArray(options.ids) ? options.ids : [options.ids];
    if (targetIds.length === 0) return { success: true };

    const rowMap = new Map<Id, T>();
    for (const row of this.#options.rows()) {
      rowMap.set(this.#options.getId(row), row);
    }

    // Apply optimistic in-memory patches
    for (const id of targetIds) {
      const row = rowMap.get(id);
      const patch =
        typeof options.patch === "function" && row
          ? options.patch(row)
          : (options.patch as Partial<T>);
      this.pendingUpdates.set(id, patch);
    }

    try {
      const result = await options.action();
      options.onSuccess?.(result);
      for (const id of targetIds) {
        this.pendingUpdates.delete(id);
      }
      return { success: true, result };
    } catch (err: any) {
      // Roll back patches
      for (const id of targetIds) {
        this.pendingUpdates.delete(id);
      }
      options.rollback?.();
      if (options.onError) {
        options.onError(err);
      } else {
        toasts.fromError(err, "Failed to update item. Changes were reverted.");
      }
      return { success: false, error: err };
    }
  }

  /**
   * General-purpose optimistic action runner for custom state changes.
   * Immediately calls `apply()`, runs `action()`, and on error calls `rollback()`.
   */
  async runOptimistic<R = unknown>(options: {
    apply: () => void;
    rollback: () => void;
    action: () => Promise<R>;
    onSuccess?: (result: R) => void;
    onError?: (error: any) => void;
  }): Promise<{ success: boolean; result?: R; error?: any }> {
    options.apply();
    try {
      const result = await options.action();
      options.onSuccess?.(result);
      return { success: true, result };
    } catch (err: any) {
      options.rollback();
      if (options.onError) {
        options.onError(err);
      } else {
        toasts.fromError(err, "Action failed. Changes were reverted.");
      }
      return { success: false, error: err };
    }
  }
}

export function createTableState<T, Id extends RowId = RowId>(
  options: TableStateOptions<T, Id>,
): TableState<T, Id> {
  return new TableState(options);
}
