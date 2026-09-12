<script lang="ts">
  import { run, stopPropagation } from "svelte/legacy";

  import { onMount, onDestroy, untrack } from "svelte";
  import {
    ListChecks,
    Search,
    Plus,
    Trash2,
    Database,
    Download,
    Folder,
    FolderOpen,
    CheckCircle2,
    CheckSquare,
    AlertCircle,
    Edit3,
    Pencil,
    GripVertical,
    Eye,
    X,
    RotateCw,
    Upload,
    Camera,
    FileText,
    FileJson,
    FileCode,
    BookOpen,
    ChevronDown,
    ExternalLink,
  } from "lucide-svelte";
  import { rulesApi, ruleExtractionApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import type {
    Rule,
    RuleFolder,
    RulesetCategory,
    RuleSnapshot,
    RuleSnapshotSourceMode,
    IdsImportResult,
    RuleSourceResponse,
  } from "../lib/types";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import RuleForm from "../lib/components/RuleForm.svelte";
  import HoverCard from "../lib/components/HoverCard.svelte";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";
  import BsddBadge from "../lib/components/BsddBadge.svelte";
  import DropdownMenu from "../lib/components/DropdownMenu.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";
  import Badge from "../lib/components/Badge.svelte";
  import Tooltip from "../lib/components/Tooltip.svelte";
  import { DropdownMenu as Menu, Tabs } from "bits-ui";
  import {
    RuleDetailsModal,
    RulesetFolderModal,
    RuleBulkEditModal,
    RulesetFolderBulkEditModal,
    RuleSnapshotModal,
    RulesetImportModal,
  } from "../lib/components/rules";
  import { describeMechanism } from "../lib/glossary";
  import { createTableState } from "../lib/tableState.svelte";

  interface Props {
    /**
     * Called when "Manual" is chosen — hand-typing a rule organized by
     * building element category lives on its own page rather than here.
     */
    onNavigateToManualRuleEditor?: () => void;
  }

  let { onNavigateToManualRuleEditor = () => {} }: Props = $props();

  // Top-level tab: Rules catalog vs saved Rule Configuration Snapshots
  let activeMainTab: "rules" | "snapshots" = $state("rules");

  // Rule-source annotation: which rule's source document is being viewed, and
  // the resolved page/snippet to jump to and highlight within it.
  let viewingSource: RuleSourceResponse | null = $state(null);
  let sourceViewError = $state("");

  async function viewRuleSource(ruleId: number) {
    sourceViewError = "";
    try {
      viewingSource = await rulesApi.getSource(ruleId);
    } catch (err: any) {
      sourceViewError = err?.message || "Could not resolve this rule's source document.";
    }
  }

  // Snapshots tab state
  let snapshots: RuleSnapshot[] = $state([]);
  let isLoadingSnapshots = $state(false);
  let snapshotsError = $state("");
  // Second table on this view: rule-configuration snapshots.
  const snapshotTable = createTableState<RuleSnapshot, number>({
    rows: () => snapshots,
    getId: (s) => s.id,
    searchFields: (s) => [s.name, s.source_ruleset_id, s.notes],
    initialSort: { field: "created_at", asc: false },
  });
  let snapshotToDelete: RuleSnapshot | null = $state(null);
  let isBulkDeleteSnapshotsModalOpen = $state(false);

  // Import IDS modal state
  let isImportIdsModalOpen = $state(false);

  // Save Snapshot modal state
  let isSaveSnapshotModalOpen = $state(false);

  const cachedRules = rulesApi.getCachedList();
  const cachedFolders = rulesApi.getCachedFolders();

  let rules: Rule[] = $state(cachedRules || []);
  let folders: RuleFolder[] = $state(cachedFolders || []);
  let isLoading = $state(!cachedRules);
  let isRefreshing = $state(false);
  let error = $state("");
  let successMessage = $state("");
  let isDeleteModalOpen = $state(false);
  let ruleToDelete: { id: number; ruleId: string } | null = $state(null);
  let isViewModalOpen = $state(false);
  let ruleToView: Rule | null = $state(null);
  let unsubscribeRules: (() => void) | null = null;

  // Filter state
  let selectedFolderId: string | null = $state(null);
  let selectedMechanism: string = $state("all");
  let selectedCategory: RulesetCategory | "all" = $state("all");
  let filterNeedsReview: boolean = $state(false);

  // Rule edit/create modal state
  let isModalOpen = $state(false);
  let editingRule: Rule | null = $state(null);

  // Sensible defaults for a brand-new rule, based on whatever the catalog is
  // currently filtered to — mirrors what the create button implied before.
  let newRuleDefaultRulesetId = $state("BUILDING-CODE-PART9");
  let newRuleDefaultCategory: RulesetCategory = $state("Arch");
  run(() => {
    newRuleDefaultRulesetId =
      selectedFolderId ||
      (selectedCategory !== "all"
        ? folders.find((f) => f.category === selectedCategory)?.ruleset_id
        : undefined) ||
      "BUILDING-CODE-PART9";
  });
  run(() => {
    newRuleDefaultCategory =
      selectedCategory !== "all"
        ? selectedCategory
        : selectedFolderId
          ? (folders.find((f) => f.ruleset_id === selectedFolderId)?.category as RulesetCategory) ||
            "Arch"
          : "Arch";
  });

  // Folder Create/Edit Modal State
  let isFolderModalOpen = $state(false);
  let isEditingFolder = $state(false);
  let folderRulesetId = $state("");
  let folderDisplayName = $state("");
  let folderDescription = $state("");
  let folderMechanismScope = $state("");
  let folderCategory: RulesetCategory = $state("Arch");

  // Folder Delete Modal State
  let isDeleteFolderModalOpen = $state(false);
  let folderToDelete: RuleFolder | null = $state(null);
  let isDeletingFolder = false;

  // Bulk Rule Modification State
  let isBulkEditRulesModalOpen = $state(false);

  // Bulk Folder Selection & Modification State
  let selectedFolderRulesetIds: string[] = $state([]);
  let isFolderSelectionMode = $state(false);
  let isBulkEditFoldersModalOpen = $state(false);
  let isBulkDeleteFoldersModalOpen = $state(false);
  let isBulkDeletingFolders = false;

  // Resizable Sidebar Splitter State
  let sidebarWidth = $state(280);
  let isDraggingDivider = $state(false);
  let dragStartX = 0;
  let dragStartWidth = 280;

  $effect(() => {
    const _orgId = authState.activeOrganizationId;
    // loadData reads/writes `rules` synchronously before its first await;
    // without untrack, that read gets tracked as a dependency of this
    // effect, and the later write to `rules` (including from the
    // cache-subscribe callback) re-fires it, causing an unbounded refetch loop.
    untrack(() => loadData(true));
  });

  async function loadData(force = false) {
    if (!rules.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }
    error = "";
    try {
      const [rulesData, foldersData] = await Promise.all([
        rulesApi.list({ organization_id: authState.activeOrganizationId }, { forceRefresh: force }),
        rulesApi.folders(undefined, { forceRefresh: force, organization_id: authState.activeOrganizationId }),
      ]);
      rules = rulesData;
      folders = foldersData;
    } catch (err: any) {
      if (!rules.length) {
        error = err.message || "Failed to load compliance rules";
      }
    } finally {
      isLoading = false;
      isRefreshing = false;
    }
  }

  onMount(() => {
    try {
      const savedWidth = localStorage.getItem("bimguard_rules_sidebar_width");
      if (savedWidth) {
        const parsed = parseInt(savedWidth, 10);
        if (!isNaN(parsed) && parsed >= 180 && parsed <= 600) {
          sidebarWidth = parsed;
        }
      }
    } catch {
      // A blocked or corrupt store just means the default sidebar width.
    }

    unsubscribeRules = rulesApi.subscribe((updatedRules) => {
      rules = updatedRules;
    });
    loadData();
  });

  onDestroy(() => {
    if (unsubscribeRules) {
      unsubscribeRules();
    }
  });

  let archCount = $derived(rules.filter((r) => (r.category || "").toLowerCase() === "arch").length);
  let pipingCount = $derived(
    rules.filter((r) => (r.category || "").toLowerCase() === "piping").length,
  );
  let seismicCount = $derived(
    rules.filter((r) => (r.category || "").toLowerCase() === "seismic").length,
  );

  let filteredFolders = $derived(
    folders.filter((f) => {
      if (selectedCategory === "all") return true;
      return (f.category || "").toLowerCase() === selectedCategory.toLowerCase();
    }),
  );

  // Search, filter, sort, paginate and select for the rules table.
  //
  // The folder selection and the needs-review toggle scope which rules the table
  // is looking at at all, so they shape the row source; the mechanism and
  // category dropdowns are the table's own filters.
  // `selectedFolderId`, `selectedMechanism`, `selectedCategory` and
  // `filterNeedsReview` also drive the folder tree, the category tabs and the
  // new-rule defaults, so they stay owned by the view and scope the row source
  // here rather than being duplicated into the table's own filter map.
  const table = createTableState<Rule, number>({
    rows: () =>
      rules.filter(
        (r) =>
          (!selectedFolderId || r.ruleset_id === selectedFolderId) &&
          (!filterNeedsReview || r.needs_review === 1) &&
          (selectedMechanism === "all" || r.mechanism === selectedMechanism) &&
          (selectedCategory === "all" ||
            (r.category || "").toLowerCase() === selectedCategory.toLowerCase()),
      ),
    getId: (r) => r.id,
    searchFields: (r) => [r.rule_id, r.description, r.property_name, r.compare_property],
    initialSort: { field: "rule_id", asc: true },
  });

  let isBulkDeleteModalOpen = $state(false);

  // ── Bulk Rules Handlers ───────────────────────────────────────────────────

  function openBulkEditRulesModal() {
    if (!table.selectedCount) return;
    isBulkEditRulesModalOpen = true;
  }

  async function handleBulkUpdateRules(payload: {
    ruleset_id?: string;
    category?: string;
    mechanism?: string;
    severity?: string;
    needs_review?: number;
  }) {
    if (!table.selectedCount) return;
    const res = await rulesApi.bulkUpdate({
      rule_ids: table.selectedIdList,
      ...payload,
    });
    successMessage = `Successfully updated ${res.success_count} rule(s).`;
    isBulkEditRulesModalOpen = false;
    table.clearSelection();
    await loadData(true);
    setTimeout(() => (successMessage = ""), 4000);
  }

  async function confirmBulkDelete() {
    if (!table.selectedCount) return;
    try {
      const res = await rulesApi.bulkDelete(table.selectedIdList);
      rules = rules.filter((r) => !table.selectedIds.has(r.id));
      table.clearSelection();
      isBulkDeleteModalOpen = false;
      successMessage = `Successfully deleted ${res.success_count} rule(s).`;
      await loadData(true);
      setTimeout(() => (successMessage = ""), 4000);
    } catch (err: any) {
      error = `Could not delete selected rules: ${err.message}`;
    }
  }

  // ── Bulk Folder Handlers ──────────────────────────────────────────────────

  function toggleFolderSelectionMode() {
    isFolderSelectionMode = !isFolderSelectionMode;
    if (!isFolderSelectionMode) {
      selectedFolderRulesetIds = [];
    }
  }

  function toggleSelectFolder(rulesetId: string, event?: Event) {
    if (event) event.stopPropagation();
    if (selectedFolderRulesetIds.includes(rulesetId)) {
      selectedFolderRulesetIds = selectedFolderRulesetIds.filter((id) => id !== rulesetId);
    } else {
      selectedFolderRulesetIds = [...selectedFolderRulesetIds, rulesetId];
    }
  }

  function openBulkEditFoldersModal() {
    if (!selectedFolderRulesetIds.length) return;
    isBulkEditFoldersModalOpen = true;
  }

  async function handleBulkUpdateFolders(payload: {
    category?: string;
    mechanism_scope?: string;
  }) {
    if (!selectedFolderRulesetIds.length) return;
    const res = await rulesApi.bulkUpdateFolders({
      ruleset_ids: selectedFolderRulesetIds,
      ...payload,
    });
    successMessage = `Successfully updated ${res.success_count} ruleset folder(s).`;
    isBulkEditFoldersModalOpen = false;
    selectedFolderRulesetIds = [];
    await loadData(true);
    setTimeout(() => (successMessage = ""), 4000);
  }

  async function confirmBulkDeleteFolders() {
    if (!selectedFolderRulesetIds.length) return;
    isBulkDeletingFolders = true;
    try {
      const res = await rulesApi.bulkDeleteFolders(selectedFolderRulesetIds);
      if (selectedFolderId && selectedFolderRulesetIds.includes(selectedFolderId)) {
        selectedFolderId = null;
      }
      successMessage = `Successfully deleted ${res.success_count} folder(s) and ${res.deleted_rules_count} member rule(s).`;
      selectedFolderRulesetIds = [];
      isBulkDeleteFoldersModalOpen = false;
      await loadData(true);
      setTimeout(() => (successMessage = ""), 4000);
    } catch (err: any) {
      error = `Could not delete selected folders: ${err.message}`;
    } finally {
      isBulkDeletingFolders = false;
    }
  }

  async function handleSeedRules() {
    try {
      const res = await ruleExtractionApi.seed();
      successMessage = `Rule library seeded successfully (${res.total_rules} rules active).`;
      await loadData();
    } catch (err: any) {
      error = `Seeding failed: ${err.message}`;
    }
  }

  // ── Snapshots tab ──────────────────────────────────────────────────────

  function switchMainTab(tab: "rules" | "snapshots") {
    activeMainTab = tab;
    if (tab === "snapshots" && snapshots.length === 0 && !isLoadingSnapshots) {
      loadSnapshots();
    }
  }

  async function loadSnapshots() {
    isLoadingSnapshots = true;
    snapshotsError = "";
    try {
      snapshots = await rulesApi.listSnapshots();
    } catch (err: any) {
      snapshotsError = err.message || "Failed to load snapshots.";
    } finally {
      isLoadingSnapshots = false;
    }
  }

  function openImportIdsModal() {
    isImportIdsModalOpen = true;
  }

  async function handleIdsImported(res: IdsImportResult) {
    successMessage = `Imported ${res.created_count} of ${res.total_parsed} rules into "${res.ruleset_id}".`;
    isImportIdsModalOpen = false;
    await loadData(true);
  }

  function openSaveSnapshotModal() {
    if (!selectedFolderId) return;
    isSaveSnapshotModalOpen = true;
  }

  async function handleSaveSnapshot(payload: {
    name: string;
    source_mode: RuleSnapshotSourceMode;
    notes: string;
  }) {
    if (!selectedFolderId) return;
    await rulesApi.createSnapshot({
      ruleset_id: selectedFolderId,
      name: payload.name,
      notes: payload.notes,
      source_mode: payload.source_mode,
    });
    successMessage = `Saved snapshot "${payload.name}".`;
    isSaveSnapshotModalOpen = false;
    snapshots = [];
    await loadSnapshots();
    setTimeout(() => (successMessage = ""), 4000);
  }

  function confirmDeleteSnapshot() {
    if (!snapshotToDelete) return;
    const id = snapshotToDelete.id;
    rulesApi
      .deleteSnapshot(id)
      .then(() => {
        snapshots = snapshots.filter((s) => s.id !== id);
        snapshotTable.selectedIds.delete(id);
      })
      .catch((err: any) => {
        snapshotsError = err.message || "Failed to delete snapshot.";
      })
      .finally(() => {
        snapshotToDelete = null;
      });
  }

  async function confirmBulkDeleteSnapshots() {
    const ids = snapshotTable.selectedIdList;
    for (const id of ids) {
      try {
        await rulesApi.deleteSnapshot(id);
      } catch (err: any) {
        snapshotsError = err.message || `Failed to delete snapshot ${id}.`;
      }
    }
    snapshots = snapshots.filter((s) => !snapshotTable.selectedIds.has(s.id));
    snapshotTable.clearSelection();
    isBulkDeleteSnapshotsModalOpen = false;
  }

  function openCreateModal() {
    editingRule = null;
    isModalOpen = true;
  }

  function openViewModal(rule: Rule) {
    ruleToView = rule;
    isViewModalOpen = true;
  }

  function openEditModal(rule: Rule) {
    editingRule = rule;
    isModalOpen = true;
  }

  async function handleRuleSaved() {
    isModalOpen = false;
    editingRule = null;
    await loadData();
  }

  function promptDelete(id: number, ruleId: string) {
    ruleToDelete = { id, ruleId };
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!ruleToDelete) return;
    try {
      await rulesApi.delete(ruleToDelete.id);
      rules = rules.filter((r) => r.id !== ruleToDelete!.id);
      ruleToDelete = null;
    } catch (err: any) {
      error = `Delete failed: ${err.message}`;
    }
  }

  // ── Folder CRUD & Resizer Handlers ──────────────────────────────────────────

  function openCreateFolderModal() {
    isEditingFolder = false;
    folderRulesetId = "";
    folderDisplayName = "";
    folderDescription = "";
    folderMechanismScope =
      selectedCategory === "Piping"
        ? "GC-001"
        : selectedCategory === "seismic"
          ? "SEISMIC"
          : "CODE";
    folderCategory = selectedCategory !== "all" ? selectedCategory : "Arch";
    isFolderModalOpen = true;
  }

  function openEditFolderModal(folder: RuleFolder, event?: MouseEvent) {
    if (event) event.stopPropagation();
    isEditingFolder = true;
    folderRulesetId = folder.ruleset_id;
    folderDisplayName = folder.display_name || folder.ruleset_id;
    folderDescription = folder.description || "";
    folderMechanismScope = folder.mechanism_scope || "CODE";
    folderCategory = (folder.category as RulesetCategory) || "Arch";
    isFolderModalOpen = true;
  }

  async function handleSaveFolder(payload: {
    ruleset_id: string;
    display_name: string;
    category: RulesetCategory;
    mechanism_scope: string;
    description: string;
  }) {
    if (isEditingFolder) {
      await rulesApi.updateFolder(payload.ruleset_id, {
        display_name: payload.display_name || payload.ruleset_id,
        description: payload.description,
        mechanism_scope: payload.mechanism_scope,
        category: payload.category,
      });
      successMessage = `Updated ruleset folder "${payload.display_name || payload.ruleset_id}"`;
    } else {
      await rulesApi.createFolder(payload);
      selectedFolderId = payload.ruleset_id;
      successMessage = `Created ruleset folder "${payload.display_name || payload.ruleset_id}"`;
    }
    isFolderModalOpen = false;
    await loadData(true);
    setTimeout(() => (successMessage = ""), 4000);
  }

  function promptDeleteFolder(folder: RuleFolder, event?: MouseEvent) {
    if (event) event.stopPropagation();
    folderToDelete = folder;
    isDeleteFolderModalOpen = true;
  }

  async function confirmDeleteFolder() {
    if (!folderToDelete) return;
    isDeletingFolder = true;
    try {
      await rulesApi.deleteFolder(folderToDelete.ruleset_id);
      if (selectedFolderId === folderToDelete.ruleset_id) {
        selectedFolderId = null;
      }
      successMessage = `Deleted folder "${folderToDelete.display_name || folderToDelete.ruleset_id}"`;
      isDeleteFolderModalOpen = false;
      folderToDelete = null;
      await loadData(true);
      setTimeout(() => (successMessage = ""), 4000);
    } catch (err: any) {
      error = `Failed to delete folder: ${err.message}`;
    } finally {
      isDeletingFolder = false;
    }
  }

  function handleDividerPointerDown(event: PointerEvent) {
    const target = event.currentTarget as HTMLElement;
    target.setPointerCapture(event.pointerId);
    isDraggingDivider = true;
    dragStartX = event.clientX;
    dragStartWidth = sidebarWidth;
  }

  function handleDividerPointerMove(event: PointerEvent) {
    if (!isDraggingDivider) return;
    const delta = event.clientX - dragStartX;
    const newWidth = Math.min(Math.max(dragStartWidth + delta, 180), 550);
    sidebarWidth = newWidth;
  }

  function handleDividerPointerUp(event: PointerEvent) {
    if (isDraggingDivider) {
      isDraggingDivider = false;
      try {
        localStorage.setItem("bimguard_rules_sidebar_width", String(sidebarWidth));
      } catch {
        // Sidebar width is a convenience; a blocked or full store is not worth reporting.
      }
    }
  }

  function handleDividerKeyDown(event: KeyboardEvent) {
    if (event.key === "ArrowLeft") {
      sidebarWidth = Math.max(sidebarWidth - 16, 180);
      try {
        localStorage.setItem("bimguard_rules_sidebar_width", String(sidebarWidth));
      } catch {
        // Sidebar width is a convenience; a blocked or full store is not worth reporting.
      }
    } else if (event.key === "ArrowRight") {
      sidebarWidth = Math.min(sidebarWidth + 16, 550);
      try {
        localStorage.setItem("bimguard_rules_sidebar_width", String(sidebarWidth));
      } catch {
        // Sidebar width is a convenience; a blocked or full store is not worth reporting.
      }
    }
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <div class="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
    <div>
      <div class="mb-1 text-xs font-bold uppercase tracking-widest text-fg-muted">Library</div>
      <h1 class="text-2xl font-bold tracking-tight text-fg-primary sm:text-3xl">Rules Catalog</h1>
      <p class="text-xs text-fg-muted sm:text-sm">
        Engineering criteria for corrosion, seismic clearance, and architectural building codes.
      </p>
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={() => loadData(true)}
        class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 p-2 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
        title="Refresh rules catalog"
      >
        <RotateCw class="h-3.5 w-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
        <span class="sr-only">Refresh</span>
      </button>

      <button
        type="button"
        onclick={handleSeedRules}
        class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
        title="Seed engine rulesets: GC-001, CC-001, MC-001"
      >
        <Database class="h-3.5 w-3.5 text-emerald-400" />
        <span>Seed Engines</span>
      </button>

      {#if activeMainTab === "rules"}
        <!-- Import/Export: one grouped menu instead of separate IDS/JSON buttons -->
        <DropdownMenu width="w-64" contentClass="rounded-2xl p-1.5">
          {#snippet trigger({ props })}
            {@const menuOpen = props["data-state"] === "open"}
            <button
              type="button"
              {...props}
              class="inline-flex items-center gap-1.5 rounded-xl border border-border-interactive bg-surface-overlay px-3.5 py-2 text-xs font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
              title="Import or export rules"
            >
              <Upload class="h-3.5 w-3.5 text-emerald-400" />
              <span>Import / Export</span>
              <ChevronDown
                class="h-3 w-3 text-fg-muted transition-transform {menuOpen ? 'rotate-180' : ''}"
              />
            </button>
          {/snippet}

          <Menu.Item
            onSelect={openImportIdsModal}
            class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left font-semibold text-fg-secondary data-highlighted:bg-surface-hover"
          >
            <Upload class="h-3.5 w-3.5 shrink-0 text-emerald-400" />
            <span class="flex-1">Import Ruleset...</span>
            <span class="text-micro font-normal text-fg-muted">IDS / JSON</span>
          </Menu.Item>

          <Menu.Separator class="my-1 border-t border-border-default" />

          {#if selectedFolderId}
            <Menu.Item>
              {#snippet child({ props })}
                <a
                  {...props}
                  href={rulesApi.getIdsExportUrl(selectedFolderId)}
                  class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left font-semibold text-fg-secondary data-highlighted:bg-surface-hover"
                >
                  <FileCode class="h-3.5 w-3.5 shrink-0 text-blue-400" />
                  <span class="flex-1">Export as IDS XML</span>
                  <Download class="h-3 w-3 text-fg-muted" />
                </a>
              {/snippet}
            </Menu.Item>
            <Menu.Item>
              {#snippet child({ props })}
                <a
                  {...props}
                  href={rulesApi.getJsonExportUrl(selectedFolderId)}
                  class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left font-semibold text-fg-secondary data-highlighted:bg-surface-hover"
                >
                  <FileJson class="h-3.5 w-3.5 shrink-0 text-amber-400" />
                  <span class="flex-1">Export as JSON</span>
                  <Download class="h-3 w-3 text-fg-muted" />
                </a>
              {/snippet}
            </Menu.Item>
          {:else}
            <p class="px-3 py-2 text-caption text-fg-muted">
              Select a ruleset folder on the left to export it.
            </p>
          {/if}
        </DropdownMenu>

        {#if selectedFolderId}
          <button
            type="button"
            onclick={openSaveSnapshotModal}
            class="inline-flex items-center gap-1.5 rounded-xl border border-border-interactive bg-surface-overlay px-3.5 py-2 text-xs font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
            title="Save the current folder's rules as a reusable snapshot"
          >
            <Camera class="h-3.5 w-3.5 text-purple-400" />
            <span>Save Snapshot</span>
          </button>
        {/if}

        <button
          type="button"
          onclick={openImportIdsModal}
          class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
          title="Parse a buildingSMART IDS (.ids/XML) or BIM-Guard JSON ruleset file into new rules"
        >
          <Upload class="h-3.5 w-3.5 text-emerald-400" />
          <span>IDS / JSON Ruleset</span>
        </button>

        <button
          type="button"
          onclick={onNavigateToManualRuleEditor}
          class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
          title="Opens the Manual Rule Editor page, organized by building element category"
        >
          <span>Manual</span>
          <ExternalLink class="h-3 w-3 opacity-60" />
        </button>

        <button
          type="button"
          onclick={openCreateModal}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
        >
          <Plus class="h-3.5 w-3.5" />
          <span>New Rule</span>
        </button>
      {/if}
    </div>
  </div>

  {#if error}
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
      {error}
    </div>
  {/if}

  {#if successMessage}
    <div
      class="flex items-center gap-2 rounded-xl border border-success-border/60 bg-success-bg/40 p-4 text-xs text-success"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-success" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Main Tab Toggle: Rules Catalog vs Saved Snapshots -->
  <div
    class="flex w-fit items-center gap-2 rounded-2xl border border-border-default bg-surface-card/60 p-1.5"
  >
    <button
      type="button"
      onclick={() => switchMainTab("rules")}
      class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {activeMainTab ===
      'rules'
        ? 'bg-accent text-white shadow-xs'
        : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
    >
      <ListChecks class="h-3.5 w-3.5" />
      <span>Rules Catalog</span>
    </button>
    <button
      type="button"
      onclick={() => switchMainTab("snapshots")}
      class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {activeMainTab ===
      'snapshots'
        ? 'bg-accent text-white shadow-xs'
        : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
    >
      <Camera class="h-3.5 w-3.5" />
      <span>Snapshots</span>
      {#if snapshots.length > 0}
        <span class="ml-0.5 text-micro opacity-75">({snapshots.length})</span>
      {/if}
    </button>
  </div>

  {#if activeMainTab === "rules"}
    <!-- Category Selector Tabs: Arch | Piping | Seismic -->
    <div
      class="flex w-fit items-center gap-2 rounded-2xl border border-border-default bg-surface-card/60 p-1.5"
    >
      <button
        type="button"
        onclick={() => {
          selectedCategory = "all";
          selectedFolderId = null;
        }}
        class="rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {selectedCategory ===
        'all'
          ? 'bg-accent text-white shadow-xs'
          : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
      >
        All Categories
      </button>
      <button
        type="button"
        onclick={() => {
          selectedCategory = "Arch";
          selectedFolderId = null;
        }}
        class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {selectedCategory ===
        'Arch'
          ? 'bg-blue-600 text-white shadow-xs'
          : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
      >
        <span class="h-2 w-2 rounded-full bg-blue-400"></span>
        <span>Arch</span>
        <span class="ml-0.5 text-micro opacity-75">({archCount})</span>
      </button>
      <button
        type="button"
        onclick={() => {
          selectedCategory = "Piping";
          selectedFolderId = null;
        }}
        class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {selectedCategory ===
        'Piping'
          ? 'bg-amber-600 text-white shadow-xs'
          : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
      >
        <span class="h-2 w-2 rounded-full bg-amber-400"></span>
        <span>Piping</span>
        <span class="ml-0.5 text-micro opacity-75">({pipingCount})</span>
      </button>
      <button
        type="button"
        onclick={() => {
          selectedCategory = "seismic";
          selectedFolderId = null;
        }}
        class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {selectedCategory ===
        'seismic'
          ? 'bg-purple-600 text-white shadow-xs'
          : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
      >
        <span class="h-2 w-2 rounded-full bg-purple-400"></span>
        <span>Seismic</span>
        <span class="ml-0.5 text-micro opacity-75">({seismicCount})</span>
      </button>
    </div>

    <!-- Main Layout: Resizable Split View (Folders Sidebar + Draggable Divider + Rules Table) -->
    <div class="relative flex flex-col items-stretch gap-0 md:flex-row">
      <!-- Folder tree sidebar -->
      <div
        class="flex w-full shrink-0 flex-col space-y-3 rounded-2xl border border-border-default bg-surface-card/60 p-4 md:w-auto md:rounded-r-none"
        style="max-width: 100%;"
        style:width={typeof window !== "undefined" && window.innerWidth >= 768
          ? `${sidebarWidth}px`
          : "100%"}
      >
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-1.5">
            <div class="text-xs font-bold uppercase tracking-wider text-fg-muted">
              Ruleset Folders
            </div>
            {#if folders.length > 0}
              <button
                type="button"
                onclick={toggleFolderSelectionMode}
                class="rounded-md p-1 transition-colors {isFolderSelectionMode ||
                selectedFolderRulesetIds.length > 0
                  ? 'bg-blue-500/10 text-blue-400'
                  : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
                title={isFolderSelectionMode
                  ? "Exit folder select mode"
                  : "Select multiple folders"}
              >
                <CheckSquare class="h-3.5 w-3.5" />
              </button>
            {/if}
          </div>
          <button
            type="button"
            onclick={openCreateFolderModal}
            class="inline-flex items-center gap-1 rounded-lg border border-border-default bg-surface-overlay px-2 py-1 text-caption font-semibold text-fg-secondary transition-colors hover:bg-blue-600 hover:text-white"
            title="Create New Ruleset Folder"
          >
            <Plus class="h-3.5 w-3.5" />
            <span>Folder</span>
          </button>
        </div>

        <!-- Folder Bulk Action Bar when folders are selected -->
        {#if selectedFolderRulesetIds.length > 0}
          <div
            class="flex items-center justify-between gap-1 rounded-xl border border-blue-800 bg-blue-950/90 p-2 text-xs text-blue-200 shadow-md duration-150 animate-in fade-in"
          >
            <div class="flex items-center gap-1 truncate text-caption font-medium">
              <span class="font-bold text-fg-primary">{selectedFolderRulesetIds.length}</span>
              <span class="truncate">selected</span>
            </div>
            <div class="flex items-center gap-1">
              <button
                type="button"
                onclick={openBulkEditFoldersModal}
                class="rounded-md bg-blue-600/40 px-2 py-1 text-micro font-medium text-white transition-colors hover:bg-blue-600"
                title="Bulk edit selected folders"
              >
                Edit
              </button>
              <button
                type="button"
                onclick={() => (isBulkDeleteFoldersModalOpen = true)}
                class="rounded-md bg-rose-600/40 px-2 py-1 text-micro font-medium text-white transition-colors hover:bg-rose-600"
                title="Bulk delete selected folders"
              >
                Delete
              </button>
              <button
                type="button"
                onclick={() => (selectedFolderRulesetIds = [])}
                class="rounded-md p-1 text-blue-300 hover:bg-blue-900/60 hover:text-fg-primary"
                title="Clear selection"
              >
                <X class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        {/if}

        <div class="max-h-[70vh] flex-1 space-y-1 overflow-y-auto pr-1">
          <button
            type="button"
            onclick={() => (selectedFolderId = null)}
            class="flex w-full items-center justify-between rounded-xl px-2.5 py-2 text-xs font-medium transition-colors {!selectedFolderId
              ? 'bg-accent text-white shadow-xs'
              : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
          >
            <div class="flex items-center gap-2">
              <FolderOpen class="h-3.5 w-3.5" />
              <span>All Rules</span>
            </div>
            <span class="text-micro opacity-75">{rules.length}</span>
          </button>

          {#each filteredFolders as folder (folder)}
            <div
              class="group/folder relative flex items-center justify-between rounded-xl text-xs font-medium transition-colors {selectedFolderId ===
              folder.ruleset_id
                ? 'bg-accent text-white shadow-xs'
                : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
            >
              {#if isFolderSelectionMode || selectedFolderRulesetIds.length > 0}
                <button
                  type="button"
                  class="flex shrink-0 cursor-pointer items-center border-0 bg-transparent py-2 pl-2.5"
                  onclick={stopPropagation((e) => toggleSelectFolder(folder.ruleset_id, e))}
                  title="Select folder"
                >
                  <input
                    type="checkbox"
                    checked={selectedFolderRulesetIds.includes(folder.ruleset_id)}
                    tabindex="-1"
                    class="pointer-events-none h-3.5 w-3.5 cursor-pointer rounded border-border-interactive bg-surface-canvas text-accent focus:ring-accent"
                  />
                </button>
              {/if}

              <button
                type="button"
                onclick={() => (selectedFolderId = folder.ruleset_id)}
                class="flex min-w-0 flex-1 items-center gap-2 truncate {isFolderSelectionMode ||
                selectedFolderRulesetIds.length > 0
                  ? 'px-1.5'
                  : 'px-2.5'} py-2 text-left"
                title="{folder.display_name} ({folder.ruleset_id})"
              >
                <Folder class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">{folder.display_name}</span>
              </button>

              <div class="flex shrink-0 items-center gap-1 pr-2">
                {#if folder.category}
                  <span
                    class="rounded px-1.5 py-0.5 font-mono text-nano font-medium {selectedFolderId ===
                    folder.ruleset_id
                      ? 'bg-white/20 text-white'
                      : folder.category?.toLowerCase() === 'piping'
                        ? 'bg-amber-500/20 text-amber-300'
                        : folder.category?.toLowerCase() === 'seismic'
                          ? 'bg-purple-500/20 text-purple-300'
                          : 'bg-blue-500/20 text-blue-300'}"
                  >
                    {folder.category?.toLowerCase() === 'seismic' ? 'Seismic' : (folder.category || 'Arch')}
                  </span>
                {/if}

                <!-- Action buttons on hover -->
                <div class="ml-1 hidden items-center gap-0.5 group-hover/folder:flex">
                  <button
                    type="button"
                    onclick={(e) => openEditFolderModal(folder, e)}
                    class="rounded p-1 text-white/80 transition-colors hover:bg-black/30 hover:text-white"
                    title="Edit Folder"
                  >
                    <Pencil class="h-3 w-3" />
                  </button>
                  <button
                    type="button"
                    onclick={(e) => promptDeleteFolder(folder, e)}
                    class="rounded p-1 text-rose-300 transition-colors hover:bg-rose-500/30 hover:text-rose-200"
                    title="Delete Folder"
                  >
                    <Trash2 class="h-3 w-3" />
                  </button>
                </div>

                <span class="ml-1 text-micro opacity-75 group-hover/folder:hidden">
                  {folder.rules.length}
                </span>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Draggable vertical resizer divider (Desktop only) -->
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <div
        role="separator"
        aria-orientation="vertical"
        aria-valuenow={sidebarWidth}
        aria-valuemin={180}
        aria-valuemax={550}
        tabindex="0"
        onpointerdown={handleDividerPointerDown}
        onpointermove={handleDividerPointerMove}
        onpointerup={handleDividerPointerUp}
        onpointercancel={handleDividerPointerUp}
        onkeydown={handleDividerKeyDown}
        class="group relative z-20 -mx-1.5 hidden w-3 cursor-col-resize select-none items-center justify-center transition-colors focus:outline-hidden md:flex"
        title="Drag to resize Ruleset Folders sidebar (or use Left/Right Arrow keys)"
      >
        <div
          class="h-full w-1 rounded-full transition-all duration-150 {isDraggingDivider
            ? 'w-1.5 bg-accent shadow-[0_0_10px_rgba(0,113,227,0.9)]'
            : 'bg-surface-overlay group-hover:bg-accent/80'}"
        ></div>
        <!-- Grip handle indicator in the middle -->
        <div
          class="pointer-events-none absolute top-1/2 flex h-7 w-4 -translate-y-1/2 items-center justify-center rounded-md border border-border-interactive bg-surface-card opacity-0 shadow-lg transition-opacity group-hover:opacity-100 {isDraggingDivider
            ? 'border-accent bg-accent opacity-100!'
            : ''}"
        >
          <GripVertical class="h-3 w-3 text-fg-muted {isDraggingDivider ? 'text-fg-primary' : ''}" />
        </div>
      </div>

      <!-- Rules Table Area -->
      <div class="min-w-0 flex-1 space-y-4 pt-4 md:pl-4 md:pt-0">
        <!-- Search & Filters -->
        <div
          class="flex flex-col items-center gap-3 rounded-2xl border border-border-default bg-surface-card/60 p-3.5 sm:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
            <input
              type="text"
              bind:value={table.search}
              placeholder="Search rules by ID, description, property..."
              class="w-full rounded-xl border border-border-default bg-surface-canvas py-1.5 pl-10 pr-4 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
            />
          </div>

          <select
            bind:value={selectedMechanism}
            class="rounded-xl border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
          >
            <option value="all">All Mechanisms</option>
            <option value="CODE">Building Code</option>
            <option value="GC-001">Galvanic (GC-001)</option>
            <option value="CC-001">Crevice (CC-001)</option>
            <option value="MC-001">Microbiological (MC-001)</option>
            <option value="SEISMIC">Seismic Clearance</option>
          </select>

          <label
            class="flex cursor-pointer items-center gap-1.5 whitespace-nowrap text-xs text-fg-muted"
          >
            <input
              type="checkbox"
              bind:checked={filterNeedsReview}
              class="rounded border-border-interactive bg-surface-canvas text-accent"
            />
            <span>Needs Review</span>
          </label>
        </div>

        <!-- Bulk Operations Bar -->
        <BulkActionBar
          selectedCount={table.selectedCount}
          itemLabel="rule"
          onClearSelection={() => table.clearSelection()}
          onBulkEdit={openBulkEditRulesModal}
          onBulkDelete={() => (isBulkDeleteModalOpen = true)}
        />

        <!-- Table Container -->
        <div class="overflow-hidden rounded-2xl border border-border-default bg-surface-card/40">
          {#if isLoading}
            <div class="p-12 text-center text-xs text-fg-muted">Loading compliance rules...</div>
          {:else if table.totalItems === 0}
            <div class="space-y-2 p-12 text-center text-xs text-fg-muted">
              <p>No rules found for this folder or filter criteria.</p>
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs text-fg-secondary">
                <thead
                  class="border-b border-border-default bg-surface-canvas text-caption font-semibold uppercase tracking-wider text-fg-muted"
                >
                  <tr>
                    <th class="w-10 px-4 py-3">
                      <TableCheckbox
                        checked={table.allFilteredSelected}
                        indeterminate={table.someFilteredSelected}
                        onchange={() => table.toggleSelectAll()}
                        title="Select or deselect all visible rules"
                        ariaLabel="Select or deselect all visible rules"
                      />
                    </th>
                    <SortHeader
                      column="rule_id"
                      sortField={table.sortField}
                      sortAsc={table.sortAsc}
                      onSort={(f) => table.toggleSort(f)}
                      customClass="px-4 py-3"
                    >
                      Rule Ref
                    </SortHeader>
                    <SortHeader
                      column="category"
                      sortField={table.sortField}
                      sortAsc={table.sortAsc}
                      onSort={(f) => table.toggleSort(f)}
                      customClass="px-4 py-3"
                    >
                      Category
                    </SortHeader>
                    <SortHeader
                      column="mechanism"
                      sortField={table.sortField}
                      sortAsc={table.sortAsc}
                      onSort={(f) => table.toggleSort(f)}
                      customClass="px-4 py-3"
                    >
                      Mechanism
                    </SortHeader>
                    <SortHeader
                      column="property_name"
                      sortField={table.sortField}
                      sortAsc={table.sortAsc}
                      onSort={(f) => table.toggleSort(f)}
                      customClass="px-4 py-3"
                    >
                      Target Property
                    </SortHeader>
                    <th class="px-4 py-3">Condition</th>
                    <SortHeader
                      column="severity"
                      sortField={table.sortField}
                      sortAsc={table.sortAsc}
                      onSort={(f) => table.toggleSort(f)}
                      customClass="px-4 py-3"
                    >
                      Severity
                    </SortHeader>
                    <th class="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-border-subtle">
                  {#each table.paginated as rule (rule.id)}
                    {@const mech = describeMechanism(rule.mechanism || "CODE")}
                    <tr
                      class="transition-colors hover:bg-surface-hover {table.isSelected(rule.id)
                        ? 'bg-surface-selected'
                        : ''}"
                    >
                      <td class="w-10 px-4 py-3">
                        <TableCheckbox
                          checked={table.isSelected(rule.id)}
                          onchange={() => table.toggleSelect(rule.id)}
                          ariaLabel="Select rule {rule.rule_id}"
                        />
                      </td>
                      <td class="px-4 py-3">
                        <!-- The description is clipped to one line here. Reading
                           it in full used to mean opening the rule; the card
                           makes it a hover, and adds the source citation the
                           reviewer needs to judge whether the rule is right. -->
                        <HoverCard
                          side="right"
                          align="start"
                          width="w-96"
                          icon={FileText}
                          title={rule.rule_id || `Rule #${rule.id}`}
                          subtitle={rule.ruleset_id || undefined}
                          triggerClass="max-w-full"
                          showFooter={!!rule.source_text || !!rule.source_document_id}
                        >
                          {#snippet trigger()}
                            <span class="block min-w-0 cursor-help text-left">
                              <span class="block font-mono font-bold text-fg-primary">
                                {rule.rule_id || `Rule #${rule.id}`}
                              </span>
                              <span class="block max-w-xs truncate text-caption text-fg-muted">
                                {rule.description || "No description"}
                              </span>
                            </span>
                          {/snippet}

                          <div class="space-y-2">
                            <p>{rule.description || "This rule carries no description."}</p>

                            <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-micro">
                              <dt class="uppercase tracking-wider text-fg-muted">Checks</dt>
                              <dd class="wrap-break-word font-mono text-fg-secondary">
                                {rule.property_set || "Pset_Compliance"}.{rule.property_name || "-"}
                              </dd>
                              <dt class="uppercase tracking-wider text-fg-muted">Category</dt>
                              <dd class="wrap-break-word font-mono text-fg-secondary">
                                {rule.rule_category || rule.category || "-"}
                              </dd>
                              <dt class="uppercase tracking-wider text-fg-muted">Severity</dt>
                              <dd class="font-mono text-fg-secondary">{rule.severity || "-"}</dd>
                            </dl>

                            {#if rule.needs_review}
                              <p class="text-micro text-amber-400">
                                Extracted automatically and not yet confirmed by a reviewer.
                              </p>
                            {/if}
                          </div>

                          {#snippet footer()}
                            <div class="space-y-1.5">
                              {#if rule.source_text}
                                <span class="block wrap-break-word italic">
                                  “{rule.source_text}”
                                </span>
                              {/if}
                              {#if rule.source_document_id}
                                <button
                                  type="button"
                                  onclick={() => viewRuleSource(rule.id)}
                                  class="inline-flex items-center gap-1 font-semibold text-accent hover:underline"
                                >
                                  <BookOpen class="h-3 w-3" />
                                  <span>View source in document</span>
                                </button>
                              {/if}
                            </div>
                          {/snippet}
                        </HoverCard>
                      </td>
                      <td class="px-4 py-3">
                        <span
                          class="inline-block rounded px-2 py-0.5 font-mono text-micro font-semibold {rule.category?.toLowerCase() ===
                          'piping'
                            ? 'border border-amber-800/50 bg-amber-950/60 text-amber-300'
                            : rule.category?.toLowerCase() === 'seismic'
                              ? 'border border-purple-800/50 bg-purple-950/60 text-purple-300'
                              : 'border border-blue-800/50 bg-blue-950/60 text-blue-300'}"
                        >
                          {rule.category?.toLowerCase() === 'seismic' ? 'Seismic' : (rule.category || "Arch")}
                        </span>
                      </td>
                      <td class="px-4 py-3">
                        {#if mech}
                          <HoverCard
                            side="top"
                            align="start"
                            width="w-80"
                            icon={Database}
                            title="{rule.mechanism || 'CODE'} — {mech.label}"
                            subtitle="Compliance mechanism"
                            showFooter={!!mech.reference}
                          >
                            {#snippet trigger()}
                              <span
                                class="inline-block cursor-help rounded bg-surface-overlay px-2 py-0.5 font-mono text-micro font-semibold text-fg-secondary"
                              >
                                {rule.mechanism || "CODE"}
                              </span>
                            {/snippet}

                            {mech.description}

                            {#snippet footer()}
                              <span class="font-mono">{mech.reference}</span>
                            {/snippet}
                          </HoverCard>
                        {:else}
                          <span
                            class="inline-block rounded bg-surface-overlay px-2 py-0.5 font-mono text-micro font-semibold text-fg-secondary"
                          >
                            {rule.mechanism || "CODE"}
                          </span>
                        {/if}
                      </td>
                      <td class="px-4 py-3 font-mono text-caption text-fg-secondary">
                        <div>
                          <BsddBadge
                            kind="property"
                            value={rule.property_name}
                            propertySet={rule.property_set}
                            fallback="-"
                          />
                        </div>
                        <div class="text-micro text-fg-muted">
                          {rule.property_set || "Pset_Compliance"}
                        </div>
                        {#if rule.target_ifc_class}
                          <div class="mt-0.5 text-micro">
                            <BsddBadge kind="class" value={rule.target_ifc_class} side="bottom" />
                          </div>
                        {/if}
                      </td>
                      <td class="px-4 py-3 font-mono text-cyan-300">
                        {#if rule.operator === "field_consistency"}
                          <div class="flex flex-col gap-0.5">
                            <span class="text-caption text-amber-300"
                              >≡ {rule.compare_property || "same element"}</span
                            >
                            {#if rule.name_pattern}
                              <span class="font-sans text-micro text-fg-muted"
                                >pattern: {rule.name_pattern}</span
                              >
                            {/if}
                          </div>
                        {:else if rule.operator === "unique_within_scope"}
                          <div class="text-caption text-purple-300">
                            <span>unique ({rule.uniqueness_scope || "building"})</span>
                          </div>
                        {:else if rule.value_min_property || rule.value_max_property}
                          <div class="text-caption text-emerald-300">
                            <span
                              >relative [{rule.value_min_property ||
                                "0"}..{rule.value_max_property || "∞"}]</span
                            >
                          </div>
                        {:else}
                          <span
                            >{rule.operator || "=="}
                            {rule.check_value || "-"}
                            {rule.unit || ""}</span
                          >
                        {/if}
                        {#if rule.needs_review}
                          <div class="mt-1">
                            <Badge variant="high" size="sm">Needs Review</Badge>
                          </div>
                        {/if}
                      </td>
                      <td class="px-4 py-3">
                        <SeverityBadge severity={rule.severity} size="xs" />
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 text-right">
                        <div class="flex items-center justify-end gap-1">
                          <Tooltip text="View rule specifications">
                            {#snippet trigger()}
                              <button
                                type="button"
                                onclick={() => openViewModal(rule)}
                                class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
                                aria-label="View rule specifications"
                              >
                                <Eye class="h-3.5 w-3.5" />
                              </button>
                            {/snippet}
                          </Tooltip>
                          <Tooltip text="Edit rule">
                            {#snippet trigger()}
                              <button
                                type="button"
                                onclick={() => openEditModal(rule)}
                                class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
                                aria-label="Edit rule"
                              >
                                <Edit3 class="h-3.5 w-3.5" />
                              </button>
                            {/snippet}
                          </Tooltip>
                          <Tooltip text="Delete rule">
                            {#snippet trigger()}
                              <button
                                type="button"
                                onclick={() => promptDelete(rule.id, rule.rule_id || "")}
                                class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-critical-bg hover:text-critical"
                                aria-label="Delete rule"
                              >
                                <Trash2 class="h-3.5 w-3.5" />
                              </button>
                            {/snippet}
                          </Tooltip>
                        </div>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>

            <TablePagination
              currentPage={table.page}
              pageSize={table.pageSize}
              totalItems={table.totalItems}
              onPageChange={(p) => (table.requestedPage = p)}
              onPageSizeChange={(size) => {
                table.pageSize = size;
                table.requestedPage = 1;
              }}
            />
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <!-- Snapshots: persisted, timestamped rule-configuration exports -->
    <div class="space-y-4">
      {#if snapshotsError}
        <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
          {snapshotsError}
        </div>
      {/if}

      <div class="flex flex-col items-center gap-3 md:flex-row">
        <div class="relative w-full flex-1">
          <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
          <input
            type="text"
            bind:value={snapshotTable.search}
            placeholder="Search snapshots by name, source folder, or notes..."
            class="w-full rounded-xl border border-border-default bg-surface-canvas py-2.5 pl-10 pr-3.5 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
          />
        </div>
      </div>

      <BulkActionBar
        selectedCount={snapshotTable.selectedCount}
        itemLabel="snapshot"
        onClearSelection={() => snapshotTable.clearSelection()}
        onBulkDelete={() => (isBulkDeleteSnapshotsModalOpen = true)}
      />

      {#if isLoadingSnapshots}
        <LoadingState message="Loading snapshots..." />
      {:else if snapshotTable.totalItems === 0}
        <EmptyState
          title="No snapshots saved yet"
          description="Save a rule folder's current configuration as a named snapshot to download it as a structured PDF later, or to keep a durable record independent of future edits."
          icon={Camera}
        />
      {:else}
        <div class="overflow-x-auto rounded-2xl border border-border-default bg-surface-card/60">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-border-default">
                <th class="w-10 px-4 py-3">
                  <TableCheckbox
                    checked={snapshotTable.allFilteredSelected}
                    indeterminate={snapshotTable.someFilteredSelected}
                    onchange={() => snapshotTable.toggleSelectAll()}
                    ariaLabel="Select all snapshots"
                  />
                </th>
                <SortHeader
                  column="name"
                  sortField={snapshotTable.sortField}
                  sortAsc={snapshotTable.sortAsc}
                  onSort={(f) => snapshotTable.toggleSort(f)}>Name</SortHeader
                >
                <SortHeader
                  column="source_ruleset_id"
                  sortField={snapshotTable.sortField}
                  sortAsc={snapshotTable.sortAsc}
                  onSort={(f) => snapshotTable.toggleSort(f)}>Source Folder</SortHeader
                >
                <th
                  class="px-4 py-3 text-left text-caption font-semibold uppercase tracking-wider text-fg-muted"
                  >Mode</th
                >
                <SortHeader
                  column="category"
                  sortField={snapshotTable.sortField}
                  sortAsc={snapshotTable.sortAsc}
                  onSort={(f) => snapshotTable.toggleSort(f)}>Category</SortHeader
                >
                <SortHeader
                  column="rule_count"
                  sortField={snapshotTable.sortField}
                  sortAsc={snapshotTable.sortAsc}
                  onSort={(f) => snapshotTable.toggleSort(f)}
                  align="center">Rules</SortHeader
                >
                <SortHeader
                  column="created_at"
                  sortField={snapshotTable.sortField}
                  sortAsc={snapshotTable.sortAsc}
                  onSort={(f) => snapshotTable.toggleSort(f)}>Saved</SortHeader
                >
                <th
                  class="px-4 py-3 text-right text-caption font-semibold uppercase tracking-wider text-fg-muted"
                  >Actions</th
                >
              </tr>
            </thead>
            <tbody>
              {#each snapshotTable.paginated as snap (snap.id)}
                <tr class="border-b border-border-subtle transition-colors hover:bg-surface-hover">
                  <td class="px-4 py-3">
                    <TableCheckbox
                      checked={snapshotTable.isSelected(snap.id)}
                      onchange={() => snapshotTable.toggleSelect(snap.id)}
                      ariaLabel={`Select snapshot ${snap.name}`}
                    />
                  </td>
                  <td class="px-4 py-3 font-medium text-fg-primary">{snap.name}</td>
                  <td class="px-4 py-3 font-mono text-fg-muted">{snap.source_ruleset_id}</td>
                  <td class="px-4 py-3">
                    <span
                      class="rounded-md border border-border-interactive bg-surface-overlay px-2 py-0.5 text-micro font-semibold uppercase text-fg-secondary"
                    >
                      {snap.source_mode}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-fg-muted">{snap.category}</td>
                  <td class="px-4 py-3 text-center text-fg-secondary">{snap.rule_count}</td>
                  <td class="px-4 py-3 text-fg-muted"
                    >{snap.created_at ? new Date(snap.created_at).toLocaleString() : "—"}</td
                  >
                  <td class="px-4 py-3">
                    <div class="flex items-center justify-end gap-1">
                      <a
                        href={rulesApi.getSnapshotPdfUrl(snap.id)}
                        class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
                        title="Download PDF"
                      >
                        <FileText class="h-3.5 w-3.5" />
                      </a>
                      <button
                        type="button"
                        onclick={() => (snapshotToDelete = snap)}
                        class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                        title="Delete snapshot"
                      >
                        <Trash2 class="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        <TablePagination
          currentPage={snapshotTable.page}
          pageSize={snapshotTable.pageSize}
          totalItems={snapshotTable.totalItems}
          onPageChange={(p) => (snapshotTable.requestedPage = p)}
          onPageSizeChange={(size) => {
            snapshotTable.pageSize = size;
            snapshotTable.requestedPage = 1;
          }}
        />
      {/if}
    </div>
  {/if}
</div>

<!-- Rule Edit/Create Modal -->
{#if isModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-2xl flex-col space-y-4 rounded-2xl border border-border-default bg-surface-card p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-border-default pb-3">
        <h2 class="text-base font-bold text-fg-primary">
          {editingRule ? "Edit Rule" : "Create New Rule"}
        </h2>
        <button
          type="button"
          onclick={() => (isModalOpen = false)}
          class="rounded-lg p-1 text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto pr-1">
        <RuleForm
          {editingRule}
          defaultRulesetId={newRuleDefaultRulesetId}
          defaultCategory={newRuleDefaultCategory}
          onCancel={() => (isModalOpen = false)}
          onSaved={handleRuleSaved}
        />
      </div>
    </div>
  </div>
{/if}

<!-- Styled Delete Confirmation Modal -->
<ConfirmModal
  bind:isOpen={isDeleteModalOpen}
  title="Delete Rule"
  message={`Are you sure you want to delete rule "${ruleToDelete?.ruleId || ""}"? This action cannot be undone.`}
  confirmText="Delete Rule"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => (ruleToDelete = null)}
/>

<!-- View Rule Details Modal -->
<RuleDetailsModal
  isOpen={isViewModalOpen}
  rule={ruleToView}
  onClose={() => (isViewModalOpen = false)}
  onEdit={(rule) => openEditModal(rule)}
/>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title="Delete Selected Compliance Rules"
  message={`Are you sure you want to delete ${table.selectedCount} selected compliance rule(s)? This action cannot be undone.`}
  confirmText="Delete Selected Rules"
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => table.clearSelection()}
/>

<!-- Create / Edit Ruleset Folder Modal -->
<RulesetFolderModal
  isOpen={isFolderModalOpen}
  isEditing={isEditingFolder}
  rulesetId={folderRulesetId}
  displayName={folderDisplayName}
  category={folderCategory}
  mechanismScope={folderMechanismScope}
  description={folderDescription}
  onClose={() => (isFolderModalOpen = false)}
  onSave={handleSaveFolder}
/>

<!-- Delete Folder Confirmation Modal -->
<ConfirmModal
  bind:isOpen={isDeleteFolderModalOpen}
  title="Delete Ruleset Folder"
  message={`Are you sure you want to delete folder "${folderToDelete?.display_name || folderToDelete?.ruleset_id || ""}"? This will delete the folder and all of its ${folderToDelete?.rules?.length ?? 0} member rules.`}
  confirmText="Delete Folder & Rules"
  danger={true}
  onConfirm={confirmDeleteFolder}
  onCancel={() => (folderToDelete = null)}
/>

<!-- Bulk Edit Rules Modal -->
<RuleBulkEditModal
  isOpen={isBulkEditRulesModalOpen}
  selectedCount={table.selectedCount}
  {folders}
  onClose={() => (isBulkEditRulesModalOpen = false)}
  onUpdate={handleBulkUpdateRules}
/>

<!-- Bulk Edit Ruleset Folders Modal -->
<RulesetFolderBulkEditModal
  isOpen={isBulkEditFoldersModalOpen}
  selectedCount={selectedFolderRulesetIds.length}
  onClose={() => (isBulkEditFoldersModalOpen = false)}
  onUpdate={handleBulkUpdateFolders}
/>

<!-- Bulk Delete Folders Confirmation Modal -->
<ConfirmModal
  bind:isOpen={isBulkDeleteFoldersModalOpen}
  title="Delete Selected Ruleset Folders"
  message={`Are you sure you want to delete ${selectedFolderRulesetIds.length} selected ruleset folder(s) and all of their member rules? This action cannot be undone.`}
  confirmText="Delete Folders & Rules"
  danger={true}
  onConfirm={confirmBulkDeleteFolders}
  onCancel={() => (isBulkDeleteFoldersModalOpen = false)}
/>

<!-- Import IDS Modal -->
<RulesetImportModal
  isOpen={isImportIdsModalOpen}
  defaultRulesetId={selectedFolderId || ""}
  onClose={() => (isImportIdsModalOpen = false)}
  onImported={handleIdsImported}
/>

<!-- Save Snapshot Modal -->
<RuleSnapshotModal
  isOpen={isSaveSnapshotModalOpen}
  folderId={selectedFolderId || ""}
  onClose={() => (isSaveSnapshotModalOpen = false)}
  onSave={handleSaveSnapshot}
/>

<!-- Delete Snapshot Confirmation Modal -->
<ConfirmModal
  isOpen={snapshotToDelete !== null}
  title="Delete Snapshot"
  message={`Are you sure you want to delete snapshot "${snapshotToDelete?.name || ""}"? This cannot be undone.`}
  confirmText="Delete Snapshot"
  danger={true}
  onConfirm={confirmDeleteSnapshot}
  onCancel={() => (snapshotToDelete = null)}
/>

<!-- Bulk Delete Snapshots Confirmation Modal -->
<ConfirmModal
  bind:isOpen={isBulkDeleteSnapshotsModalOpen}
  title="Delete Selected Snapshots"
  message={`Are you sure you want to delete ${snapshotTable.selectedCount} selected snapshot(s)? This cannot be undone.`}
  confirmText="Delete Snapshots"
  danger={true}
  onConfirm={confirmBulkDeleteSnapshots}
  onCancel={() => (isBulkDeleteSnapshotsModalOpen = false)}
/>

<!-- Rule Source Annotation Modal: jumps to and highlights the page/snippet a rule was traced back to -->
{#if viewingSource}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-border-default px-6 py-4">
        <div>
          <h2 class="text-base font-bold tracking-tight text-fg-primary">{viewingSource.filename}</h2>
          {#if viewingSource.page_number}
            <p class="mt-0.5 text-xs text-fg-muted">Page {viewingSource.page_number}</p>
          {/if}
        </div>
        <button
          type="button"
          onclick={() => (viewingSource = null)}
          class="rounded-lg p-1 text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
      <div class="flex-1 overflow-hidden">
        <DocumentViewer
          documentId={viewingSource.document_id}
          page={viewingSource.page_number}
          highlightText={viewingSource.snippet}
          bbox={viewingSource.bbox}
        />
      </div>
    </div>
  </div>
{/if}

{#if sourceViewError}
  <div class="fixed bottom-6 right-6 z-50 max-w-sm rounded-xl border border-critical-border bg-critical-bg px-4 py-3 text-xs text-critical shadow-2xl backdrop-blur-md">
    <div class="flex items-start justify-between gap-3">
      <span>{sourceViewError}</span>
      <button type="button" onclick={() => (sourceViewError = "")} class="shrink-0 text-critical hover:text-fg-primary" aria-label="Dismiss error">
        <X class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
{/if}
