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
  import RulesetImportForm from "../lib/components/RulesetImportForm.svelte";
  import HoverCard from "../lib/components/HoverCard.svelte";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";
  import BsddBadge from "../lib/components/BsddBadge.svelte";
  import { describeMechanism } from "../lib/glossary";
  import { createTableState } from "../lib/tableState.svelte";

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

  // Import/Export dropdown menu state (header actions)
  let isImportExportMenuOpen = $state(false);
  let importExportMenuEl: HTMLDivElement | null = $state(null);

  function handleImportExportOutsideClick(event: MouseEvent) {
    if (importExportMenuEl && !importExportMenuEl.contains(event.target as Node)) {
      isImportExportMenuOpen = false;
    }
  }

  $effect(() => {
    if (!isImportExportMenuOpen) return;
    window.addEventListener("click", handleImportExportOutsideClick);
    return () => window.removeEventListener("click", handleImportExportOutsideClick);
  });

  // Save Snapshot modal state
  let isSaveSnapshotModalOpen = $state(false);
  let saveSnapshotName = $state("");
  let saveSnapshotNotes = $state("");
  let saveSnapshotSourceMode: RuleSnapshotSourceMode = $state("manual");
  let isSavingSnapshot = $state(false);
  let saveSnapshotError = $state("");

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
  let folderModalError = $state("");
  let isSavingFolder = $state(false);

  // Folder Delete Modal State
  let isDeleteFolderModalOpen = $state(false);
  let folderToDelete: RuleFolder | null = $state(null);
  let isDeletingFolder = false;

  // Bulk Rule Modification State
  let isBulkEditRulesModalOpen = $state(false);
  let bulkRuleRulesetId = $state("__keep__");
  let bulkRuleCategory: RulesetCategory | "__keep__" = $state("__keep__");
  let bulkRuleMechanism = $state("__keep__");
  let bulkRuleSeverity = $state("__keep__");
  let bulkRuleNeedsReview: "0" | "1" | "__keep__" = $state("__keep__");
  let isBulkUpdatingRules = $state(false);
  let bulkRulesModalError = $state("");

  // Bulk Folder Selection & Modification State
  let selectedFolderRulesetIds: string[] = $state([]);
  let isFolderSelectionMode = $state(false);
  let isBulkEditFoldersModalOpen = $state(false);
  let bulkFolderCategory: RulesetCategory | "__keep__" = $state("__keep__");
  let bulkFolderMechanismScope = $state("__keep__");
  let isBulkUpdatingFolders = $state(false);
  let bulkFoldersModalError = $state("");
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
    bulkRuleRulesetId = "__keep__";
    bulkRuleCategory = "__keep__";
    bulkRuleMechanism = "__keep__";
    bulkRuleSeverity = "__keep__";
    bulkRuleNeedsReview = "__keep__";
    bulkRulesModalError = "";
    isBulkEditRulesModalOpen = true;
  }

  async function handleBulkUpdateRules() {
    if (!table.selectedCount) return;
    isBulkUpdatingRules = true;
    bulkRulesModalError = "";
    try {
      const payload: any = { rule_ids: table.selectedIdList };
      if (bulkRuleRulesetId !== "__keep__") payload.ruleset_id = bulkRuleRulesetId;
      if (bulkRuleCategory !== "__keep__") payload.category = bulkRuleCategory;
      if (bulkRuleMechanism !== "__keep__") payload.mechanism = bulkRuleMechanism;
      if (bulkRuleSeverity !== "__keep__") payload.severity = bulkRuleSeverity;
      if (bulkRuleNeedsReview !== "__keep__")
        payload.needs_review = parseInt(bulkRuleNeedsReview, 10);

      const res = await rulesApi.bulkUpdate(payload);
      successMessage = `Successfully updated ${res.success_count} rule(s).`;
      isBulkEditRulesModalOpen = false;
      table.clearSelection();
      await loadData(true);
      setTimeout(() => (successMessage = ""), 4000);
    } catch (err: any) {
      bulkRulesModalError = err.message || "Failed to update rules in bulk.";
    } finally {
      isBulkUpdatingRules = false;
    }
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
    bulkFolderCategory = "__keep__";
    bulkFolderMechanismScope = "__keep__";
    bulkFoldersModalError = "";
    isBulkEditFoldersModalOpen = true;
  }

  async function handleBulkUpdateFolders() {
    if (!selectedFolderRulesetIds.length) return;
    isBulkUpdatingFolders = true;
    bulkFoldersModalError = "";
    try {
      const payload: any = { ruleset_ids: selectedFolderRulesetIds };
      if (bulkFolderCategory !== "__keep__") payload.category = bulkFolderCategory;
      if (bulkFolderMechanismScope !== "__keep__")
        payload.mechanism_scope = bulkFolderMechanismScope;

      const res = await rulesApi.bulkUpdateFolders(payload);
      successMessage = `Successfully updated ${res.success_count} ruleset folder(s).`;
      isBulkEditFoldersModalOpen = false;
      selectedFolderRulesetIds = [];
      await loadData(true);
      setTimeout(() => (successMessage = ""), 4000);
    } catch (err: any) {
      bulkFoldersModalError = err.message || "Failed to update folders in bulk.";
    } finally {
      isBulkUpdatingFolders = false;
    }
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
    saveSnapshotName = selectedFolderId;
    saveSnapshotNotes = "";
    const folder = folders.find((f) => f.ruleset_id === selectedFolderId);
    saveSnapshotSourceMode = "manual";
    saveSnapshotError = "";
    isSaveSnapshotModalOpen = true;
  }

  async function handleSaveSnapshot() {
    if (!selectedFolderId || !saveSnapshotName.trim()) {
      saveSnapshotError = "Please provide a snapshot name.";
      return;
    }
    isSavingSnapshot = true;
    saveSnapshotError = "";
    try {
      await rulesApi.createSnapshot({
        ruleset_id: selectedFolderId,
        name: saveSnapshotName.trim(),
        notes: saveSnapshotNotes.trim(),
        source_mode: saveSnapshotSourceMode,
      });
      successMessage = `Saved snapshot "${saveSnapshotName.trim()}".`;
      isSaveSnapshotModalOpen = false;
      snapshots = [];
      await loadSnapshots();
    } catch (err: any) {
      saveSnapshotError = err.message || "Failed to save snapshot.";
    } finally {
      isSavingSnapshot = false;
    }
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
    folderModalError = "";
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
    folderModalError = "";
    isFolderModalOpen = true;
  }

  async function handleSaveFolder() {
    if (!folderRulesetId.trim()) {
      folderModalError = "Ruleset ID is required.";
      return;
    }
    isSavingFolder = true;
    folderModalError = "";
    try {
      if (isEditingFolder) {
        await rulesApi.updateFolder(folderRulesetId, {
          display_name: folderDisplayName.trim() || folderRulesetId.trim(),
          description: folderDescription.trim(),
          mechanism_scope: folderMechanismScope.trim(),
          category: folderCategory,
        });
        successMessage = `Updated ruleset folder "${folderDisplayName || folderRulesetId}"`;
      } else {
        await rulesApi.createFolder({
          ruleset_id: folderRulesetId.trim(),
          display_name: folderDisplayName.trim() || folderRulesetId.trim(),
          description: folderDescription.trim(),
          mechanism_scope: folderMechanismScope.trim(),
          category: folderCategory,
        });
        selectedFolderId = folderRulesetId.trim();
        successMessage = `Created ruleset folder "${folderDisplayName || folderRulesetId}"`;
      }
      isFolderModalOpen = false;
      await loadData(true);
      setTimeout(() => (successMessage = ""), 4000);
    } catch (err: any) {
      folderModalError = err.message || "Failed to save ruleset folder.";
    } finally {
      isSavingFolder = false;
    }
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
      <div class="mb-1 text-xs font-bold uppercase tracking-widest text-slate-400">Library</div>
      <h1 class="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">Rules Catalog</h1>
      <p class="text-xs text-slate-400 sm:text-sm">
        Engineering criteria for corrosion, seismic clearance, and architectural building codes.
      </p>
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={() => loadData(true)}
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900/60 p-2 text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
        title="Refresh rules catalog"
      >
        <RotateCw class="h-3.5 w-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
        <span class="sr-only">Refresh</span>
      </button>

      <button
        type="button"
        onclick={handleSeedRules}
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
        title="Seed engine rulesets: GC-001, CC-001, MC-001"
      >
        <Database class="h-3.5 w-3.5 text-emerald-400" />
        <span>Seed Engines</span>
      </button>

      {#if activeMainTab === "rules"}
        <!-- Import/Export: one grouped menu instead of separate IDS/JSON buttons -->
        <div class="relative" bind:this={importExportMenuEl}>
          <button
            type="button"
            onclick={() => (isImportExportMenuOpen = !isImportExportMenuOpen)}
            class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
            title="Import or export rules"
            aria-expanded={isImportExportMenuOpen}
            aria-haspopup="menu"
          >
            <Upload class="h-3.5 w-3.5 text-emerald-400" />
            <span>Import / Export</span>
            <ChevronDown
              class="h-3 w-3 text-slate-400 transition-transform {isImportExportMenuOpen
                ? 'rotate-180'
                : ''}"
            />
          </button>

          {#if isImportExportMenuOpen}
            <div
              role="menu"
              class="absolute right-0 z-30 mt-2 w-64 space-y-1 rounded-2xl border border-slate-800 bg-slate-900 p-1.5 text-xs shadow-2xl duration-100 animate-in fade-in slide-in-from-top-1"
            >
              <button
                type="button"
                role="menuitem"
                onclick={() => {
                  isImportExportMenuOpen = false;
                  openImportIdsModal();
                }}
                class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left font-semibold text-slate-200 hover:bg-slate-800"
              >
                <Upload class="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                <span class="flex-1">Import Ruleset...</span>
                <span class="text-micro font-normal text-slate-500">IDS / JSON</span>
              </button>

              <div class="my-1 border-t border-slate-800"></div>

              {#if selectedFolderId}
                <a
                  role="menuitem"
                  href={rulesApi.getIdsExportUrl(selectedFolderId)}
                  onclick={() => (isImportExportMenuOpen = false)}
                  class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left font-semibold text-slate-200 hover:bg-slate-800"
                >
                  <FileCode class="h-3.5 w-3.5 shrink-0 text-blue-400" />
                  <span class="flex-1">Export as IDS XML</span>
                  <Download class="h-3 w-3 text-slate-500" />
                </a>
                <a
                  role="menuitem"
                  href={rulesApi.getJsonExportUrl(selectedFolderId)}
                  onclick={() => (isImportExportMenuOpen = false)}
                  class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left font-semibold text-slate-200 hover:bg-slate-800"
                >
                  <FileJson class="h-3.5 w-3.5 shrink-0 text-amber-400" />
                  <span class="flex-1">Export as JSON</span>
                  <Download class="h-3 w-3 text-slate-500" />
                </a>
              {:else}
                <p class="px-3 py-2 text-caption text-slate-500">
                  Select a ruleset folder on the left to export it.
                </p>
              {/if}
            </div>
          {/if}
        </div>

        {#if selectedFolderId}
          <button
            type="button"
            onclick={openSaveSnapshotModal}
            class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
            title="Save the current folder's rules as a reusable snapshot"
          >
            <Camera class="h-3.5 w-3.5 text-purple-400" />
            <span>Save Snapshot</span>
          </button>
        {/if}

        <button
          type="button"
          onclick={openCreateModal}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
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
      class="flex items-center gap-2 rounded-xl border border-emerald-800 bg-emerald-950/50 p-4 text-xs text-emerald-300"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Main Tab Toggle: Rules Catalog vs Saved Snapshots -->
  <div
    class="flex w-fit items-center gap-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-1.5"
  >
    <button
      type="button"
      onclick={() => switchMainTab("rules")}
      class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {activeMainTab ===
      'rules'
        ? 'bg-accent text-white shadow-sm'
        : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
    >
      <ListChecks class="h-3.5 w-3.5" />
      <span>Rules Catalog</span>
    </button>
    <button
      type="button"
      onclick={() => switchMainTab("snapshots")}
      class="inline-flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {activeMainTab ===
      'snapshots'
        ? 'bg-accent text-white shadow-sm'
        : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
    >
      <Camera class="h-3.5 w-3.5" />
      <span>Snapshots</span>
      {#if snapshots.length > 0}
        <span class="ml-0.5 text-micro opacity-75">({snapshots.length})</span>
      {/if}
    </button>
  </div>

  {#if activeMainTab === "rules"}
    <!-- Category Selector Tabs: Arch | Piping | seismic -->
    <div
      class="flex w-fit items-center gap-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-1.5"
    >
      <button
        type="button"
        onclick={() => {
          selectedCategory = "all";
          selectedFolderId = null;
        }}
        class="rounded-xl px-3.5 py-1.5 text-xs font-semibold transition-all {selectedCategory ===
        'all'
          ? 'bg-accent text-white shadow-sm'
          : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
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
          ? 'bg-blue-600 text-white shadow-sm'
          : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
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
          ? 'bg-amber-600 text-white shadow-sm'
          : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
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
          ? 'bg-purple-600 text-white shadow-sm'
          : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
      >
        <span class="h-2 w-2 rounded-full bg-purple-400"></span>
        <span>seismic</span>
        <span class="ml-0.5 text-micro opacity-75">({seismicCount})</span>
      </button>
    </div>

    <!-- Main Layout: Resizable Split View (Folders Sidebar + Draggable Divider + Rules Table) -->
    <div class="relative flex flex-col items-stretch gap-0 md:flex-row">
      <!-- Folder tree sidebar -->
      <div
        class="flex w-full shrink-0 flex-col space-y-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 md:w-auto md:rounded-r-none"
        style="max-width: 100%;"
        style:width={typeof window !== "undefined" && window.innerWidth >= 768
          ? `${sidebarWidth}px`
          : "100%"}
      >
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-1.5">
            <div class="text-xs font-bold uppercase tracking-wider text-slate-400">
              Ruleset Folders
            </div>
            {#if folders.length > 0}
              <button
                type="button"
                onclick={toggleFolderSelectionMode}
                class="rounded-md p-1 transition-colors {isFolderSelectionMode ||
                selectedFolderRulesetIds.length > 0
                  ? 'bg-blue-500/10 text-blue-400'
                  : 'text-slate-500 hover:bg-slate-800 hover:text-slate-50'}"
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
            class="inline-flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-800/80 px-2 py-1 text-caption font-semibold text-slate-300 transition-colors hover:bg-blue-600 hover:text-white"
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
              <span class="font-bold text-slate-50">{selectedFolderRulesetIds.length}</span>
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
                class="rounded-md p-1 text-blue-300 hover:bg-blue-900/60 hover:text-slate-50"
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
              ? 'bg-accent text-white shadow-sm'
              : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
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
                ? 'bg-accent text-white shadow-sm'
                : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-50'}"
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
                    class="pointer-events-none h-3.5 w-3.5 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent focus:ring-accent"
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
                      : folder.category === 'Piping'
                        ? 'bg-amber-500/20 text-amber-300'
                        : folder.category === 'seismic'
                          ? 'bg-purple-500/20 text-purple-300'
                          : 'bg-blue-500/20 text-blue-300'}"
                  >
                    {folder.category}
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
        class="group relative z-20 -mx-1.5 hidden w-3 cursor-col-resize select-none items-center justify-center transition-colors focus:outline-none md:flex"
        title="Drag to resize Ruleset Folders sidebar (or use Left/Right Arrow keys)"
      >
        <div
          class="h-full w-1 rounded-full transition-all duration-150 {isDraggingDivider
            ? 'w-1.5 bg-accent shadow-[0_0_10px_rgba(0,113,227,0.9)]'
            : 'bg-slate-800 group-hover:bg-accent/80'}"
        ></div>
        <!-- Grip handle indicator in the middle -->
        <div
          class="pointer-events-none absolute top-1/2 flex h-7 w-4 -translate-y-1/2 items-center justify-center rounded-md border border-slate-700 bg-slate-900 opacity-0 shadow-lg transition-opacity group-hover:opacity-100 {isDraggingDivider
            ? 'border-accent bg-accent !opacity-100'
            : ''}"
        >
          <GripVertical class="h-3 w-3 text-slate-400 {isDraggingDivider ? 'text-slate-50' : ''}" />
        </div>
      </div>

      <!-- Rules Table Area -->
      <div class="min-w-0 flex-1 space-y-4 pt-4 md:pl-4 md:pt-0">
        <!-- Search & Filters -->
        <div
          class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-3.5 sm:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              bind:value={table.search}
              placeholder="Search rules by ID, description, property..."
              class="w-full rounded-xl border border-slate-800 bg-slate-950 py-1.5 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>

          <select
            bind:value={selectedMechanism}
            class="rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="all">All Mechanisms</option>
            <option value="CODE">Building Code</option>
            <option value="GC-001">Galvanic (GC-001)</option>
            <option value="CC-001">Crevice (CC-001)</option>
            <option value="MC-001">Microbiological (MC-001)</option>
            <option value="SEISMIC">Seismic Clearance</option>
          </select>

          <label
            class="flex cursor-pointer items-center gap-1.5 whitespace-nowrap text-xs text-slate-400"
          >
            <input
              type="checkbox"
              bind:checked={filterNeedsReview}
              class="rounded border-slate-700 bg-slate-950 text-accent"
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
        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
          {#if isLoading}
            <div class="p-12 text-center text-xs text-slate-400">Loading compliance rules...</div>
          {:else if table.totalItems === 0}
            <div class="space-y-2 p-12 text-center text-xs text-slate-500">
              <p>No rules found for this folder or filter criteria.</p>
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs text-slate-300">
                <thead
                  class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
                >
                  <tr>
                    <th class="w-10 px-4 py-3">
                      <input
                        type="checkbox"
                        checked={table.allFilteredSelected}
                        indeterminate={table.someFilteredSelected}
                        onchange={() => table.toggleSelectAll()}
                        class="h-4 w-4 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent focus:ring-accent"
                        title="Select or deselect all visible rules"
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
                <tbody class="divide-y divide-slate-800/60">
                  {#each table.paginated as rule (rule.id)}
                    {@const mech = describeMechanism(rule.mechanism || "CODE")}
                    <tr
                      class="transition-colors hover:bg-slate-900/60 {table.isSelected(rule.id)
                        ? 'bg-blue-950/20'
                        : ''}"
                    >
                      <td class="w-10 px-4 py-3">
                        <input
                          type="checkbox"
                          checked={table.isSelected(rule.id)}
                          onchange={() => table.toggleSelect(rule.id)}
                          class="h-4 w-4 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent focus:ring-accent"
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
                              <span class="block font-mono font-bold text-slate-100">
                                {rule.rule_id || `Rule #${rule.id}`}
                              </span>
                              <span class="block max-w-xs truncate text-caption text-slate-400">
                                {rule.description || "No description"}
                              </span>
                            </span>
                          {/snippet}

                          <div class="space-y-2">
                            <p>{rule.description || "This rule carries no description."}</p>

                            <dl class="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-micro">
                              <dt class="uppercase tracking-wider text-slate-500">Checks</dt>
                              <dd class="break-words font-mono text-slate-200">
                                {rule.property_set || "Pset_Compliance"}.{rule.property_name || "-"}
                              </dd>
                              <dt class="uppercase tracking-wider text-slate-500">Category</dt>
                              <dd class="break-words font-mono text-slate-200">
                                {rule.rule_category || rule.category || "-"}
                              </dd>
                              <dt class="uppercase tracking-wider text-slate-500">Severity</dt>
                              <dd class="font-mono text-slate-200">{rule.severity || "-"}</dd>
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
                                <span class="block break-words italic">
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
                          class="inline-block rounded px-2 py-0.5 font-mono text-micro font-semibold {rule.category ===
                          'Piping'
                            ? 'border border-amber-800/50 bg-amber-950/60 text-amber-300'
                            : rule.category === 'seismic'
                              ? 'border border-purple-800/50 bg-purple-950/60 text-purple-300'
                              : 'border border-blue-800/50 bg-blue-950/60 text-blue-300'}"
                        >
                          {rule.category || "Arch"}
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
                                class="inline-block cursor-help rounded bg-slate-800 px-2 py-0.5 font-mono text-micro font-semibold text-slate-300"
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
                            class="inline-block rounded bg-slate-800 px-2 py-0.5 font-mono text-micro font-semibold text-slate-300"
                          >
                            {rule.mechanism || "CODE"}
                          </span>
                        {/if}
                      </td>
                      <td class="px-4 py-3 font-mono text-caption text-slate-300">
                        <div>
                          <BsddBadge
                            kind="property"
                            value={rule.property_name}
                            propertySet={rule.property_set}
                            fallback="-"
                          />
                        </div>
                        <div class="text-micro text-slate-500">
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
                              <span class="font-sans text-micro text-slate-500"
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
                          <span
                            class="py-0.2 mt-1 inline-block rounded border border-amber-800 bg-amber-950/70 px-1.5 font-sans text-nano font-medium text-amber-400"
                          >
                            Needs Review
                          </span>
                        {/if}
                      </td>
                      <td class="px-4 py-3">
                        <span
                          class="inline-block rounded px-2 py-0.5 text-micro font-semibold {rule.severity ===
                            'Critical' || rule.severity === 'mandatory'
                            ? 'border border-red-800/60 bg-red-950/60 text-red-400'
                            : rule.severity === 'High'
                              ? 'border border-orange-800/60 bg-orange-950/60 text-orange-400'
                              : 'border border-yellow-800/60 bg-yellow-950/60 text-yellow-400'}"
                        >
                          {rule.severity}
                        </span>
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 text-right">
                        <div class="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onclick={() => openViewModal(rule)}
                            class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
                            title="View rule specifications"
                          >
                            <Eye class="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onclick={() => openEditModal(rule)}
                            class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
                            title="Edit rule"
                          >
                            <Edit3 class="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onclick={() => promptDelete(rule.id, rule.rule_id || "")}
                            class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                            title="Delete rule"
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
          <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            bind:value={snapshotTable.search}
            placeholder="Search snapshots by name, source folder, or notes..."
            class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2.5 pl-10 pr-3.5 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
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
        <div class="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/60">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-slate-800">
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
                  class="px-4 py-3 text-left text-caption font-semibold uppercase tracking-wider text-slate-400"
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
                  class="px-4 py-3 text-right text-caption font-semibold uppercase tracking-wider text-slate-400"
                  >Actions</th
                >
              </tr>
            </thead>
            <tbody>
              {#each snapshotTable.paginated as snap (snap.id)}
                <tr class="border-b border-slate-800/60 transition-colors hover:bg-slate-800/30">
                  <td class="px-4 py-3">
                    <TableCheckbox
                      checked={snapshotTable.isSelected(snap.id)}
                      onchange={() => snapshotTable.toggleSelect(snap.id)}
                      ariaLabel={`Select snapshot ${snap.name}`}
                    />
                  </td>
                  <td class="px-4 py-3 font-medium text-slate-50">{snap.name}</td>
                  <td class="px-4 py-3 font-mono text-slate-400">{snap.source_ruleset_id}</td>
                  <td class="px-4 py-3">
                    <span
                      class="rounded-md border border-slate-700 bg-slate-800 px-2 py-0.5 text-micro font-semibold uppercase text-slate-300"
                    >
                      {snap.source_mode}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-slate-400">{snap.category}</td>
                  <td class="px-4 py-3 text-center text-slate-300">{snap.rule_count}</td>
                  <td class="px-4 py-3 text-slate-400"
                    >{snap.created_at ? new Date(snap.created_at).toLocaleString() : "—"}</td
                  >
                  <td class="px-4 py-3">
                    <div class="flex items-center justify-end gap-1">
                      <a
                        href={rulesApi.getSnapshotPdfUrl(snap.id)}
                        class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
                        title="Download PDF"
                      >
                        <FileText class="h-3.5 w-3.5" />
                      </a>
                      <button
                        type="button"
                        onclick={() => (snapshotToDelete = snap)}
                        class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
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
      class="flex max-h-[90vh] w-full max-w-2xl flex-col space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 class="text-base font-bold text-slate-50">
          {editingRule ? "Edit Rule" : "Create New Rule"}
        </h2>
        <button
          type="button"
          onclick={() => (isModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
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
{#if isViewModalOpen && ruleToView}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-purple-500/20 bg-purple-500/10 p-2 text-purple-400">
            <ListChecks class="h-5 w-5" />
          </div>
          <div>
            <h2 class="font-mono text-base font-bold text-slate-50">
              {ruleToView.rule_id || `Rule #${ruleToView.id}`}
            </h2>
            <p class="text-xs text-slate-400">Rule Specification &amp; Conditions</p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (isViewModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="space-y-4 overflow-y-auto p-6 text-xs">
        <div>
          <span class="mb-1 block font-semibold text-slate-400">Description</span>
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-slate-200">
            {ruleToView.description || "No description provided."}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-2.5">
            <span class="block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Category</span
            >
            <span class="font-mono font-semibold text-slate-50"
              >{ruleToView.category || "Arch"}</span
            >
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-2.5">
            <span class="block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Mechanism</span
            >
            <span class="font-mono font-semibold text-slate-50"
              >{ruleToView.mechanism || "CODE"}</span
            >
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-2.5">
            <span class="block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Severity</span
            >
            <span class="font-semibold text-amber-400">{ruleToView.severity}</span>
          </div>

          <div class="rounded-xl border border-slate-800 bg-slate-950/40 p-2.5">
            <span class="block text-micro font-semibold uppercase tracking-wider text-slate-500"
              >Ruleset / Folder</span
            >
            <span class="block truncate font-mono text-slate-300"
              >{ruleToView.ruleset_id || "Global"}</span
            >
          </div>
        </div>

        <div class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
          <span class="block text-micro font-semibold uppercase tracking-wider text-slate-400"
            >Target &amp; Condition</span
          >
          <div class="grid grid-cols-2 gap-2 font-mono text-caption">
            <div>
              <span class="text-slate-500">Pset:</span>
              <span class="text-slate-300">{ruleToView.property_set || "Pset_Compliance"}</span>
            </div>
            <div>
              <span class="text-slate-500">Property:</span>
              <span class="text-slate-300">{ruleToView.property_name || "—"}</span>
            </div>
            <div>
              <span class="text-slate-500">Operator:</span>
              <span class="text-cyan-300">{ruleToView.operator || "=="}</span>
            </div>
            <div>
              <span class="text-slate-500">Target Value:</span>
              <span class="text-emerald-300"
                >{ruleToView.check_value ||
                  (ruleToView.value_min
                    ? `[${ruleToView.value_min}..${ruleToView.value_max}]`
                    : "—")}
                {ruleToView.unit || ""}</span
              >
            </div>
          </div>
          {#if ruleToView.compare_property}
            <div class="pt-1 font-mono text-caption text-amber-300">
              Compare with: {ruleToView.compare_property}
            </div>
          {/if}
        </div>

        <div>
          <span class="mb-1 block text-micro font-semibold uppercase tracking-wider text-slate-500"
            >Raw JSON Definition</span
          >
          <pre
            class="max-h-40 overflow-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-caption text-slate-400">{JSON.stringify(
              ruleToView,
              null,
              2,
            )}</pre>
        </div>
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-between border-t border-slate-800 bg-slate-950/60 px-6 py-3"
      >
        <button
          type="button"
          onclick={() => {
            isViewModalOpen = false;
            if (ruleToView) openEditModal(ruleToView);
          }}
          class="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-slate-50 transition-colors hover:bg-slate-700"
        >
          <Edit3 class="h-3.5 w-3.5" />
          <span>Edit this Rule</span>
        </button>

        <button
          type="button"
          onclick={() => (isViewModalOpen = false)}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

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
{#if isFolderModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            {#if isEditingFolder}
              <Pencil class="h-5 w-5" />
            {:else}
              <Folder class="h-5 w-5" />
            {/if}
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              {isEditingFolder ? `Edit Folder: ${folderRulesetId}` : "Create Ruleset Folder"}
            </h2>
            <p class="text-xs text-slate-400">
              {isEditingFolder
                ? "Update folder name, category, and scope"
                : "Organize compliance rules under a new domain ruleset"}
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (isFolderModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="flex-1 space-y-4 overflow-y-auto p-6 text-xs">
        {#if folderModalError}
          <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-rose-300">
            {folderModalError}
          </div>
        {/if}

        <div class="space-y-1.5">
          <label for="folder-ruleset-id" class="block font-semibold text-slate-300">
            Ruleset Identifier (ID) <span class="text-rose-400">*</span>
          </label>
          <input
            id="folder-ruleset-id"
            type="text"
            bind:value={folderRulesetId}
            disabled={isEditingFolder}
            placeholder="e.g. BUILDING-CODE-PART3 or GC-001"
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 font-mono text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          {#if !isEditingFolder}
            <p class="text-caption text-slate-500">
              Unique ID used to link member rules (e.g. CODE-2024-STAIRS, GC-001, SEISMIC-CLEARANCE).
            </p>
          {/if}
        </div>

        <div class="space-y-1.5">
          <label for="folder-display-name" class="block font-semibold text-slate-300">
            Display Name
          </label>
          <input
            id="folder-display-name"
            type="text"
            bind:value={folderDisplayName}
            placeholder="e.g. Building Code Part 3 - Fire Protection & Safety"
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label for="folder-category" class="block font-semibold text-slate-300">
              Domain Category
            </label>
            <select
              id="folder-category"
              bind:value={folderCategory}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="Arch">Arch (Architectural)</option>
              <option value="Piping">Piping (Corrosion)</option>
              <option value="seismic">seismic (Clearance)</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label for="folder-mechanism-scope" class="block font-semibold text-slate-300">
              Mechanism Scope
            </label>
            <select
              id="folder-mechanism-scope"
              bind:value={folderMechanismScope}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="CODE">CODE (Building Code)</option>
              <option value="GC-001">GC-001 (Galvanic)</option>
              <option value="CC-001">CC-001 (Crevice)</option>
              <option value="MC-001">MC-001 (Microbiological)</option>
              <option value="SEISMIC">SEISMIC (Clearance Detection)</option>
            </select>
          </div>
        </div>

        <div class="space-y-1.5">
          <label for="folder-desc" class="block font-semibold text-slate-300"> Description </label>
          <textarea
            id="folder-desc"
            rows="3"
            bind:value={folderDescription}
            placeholder="Regulatory standard, scope notes, or compliance criteria..."
            class="w-full resize-y rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          ></textarea>
        </div>
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950 px-6 py-3"
      >
        <button
          type="button"
          onclick={() => (isFolderModalOpen = false)}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSavingFolder || !folderRulesetId.trim()}
          onclick={handleSaveFolder}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          <span
            >{isSavingFolder
              ? "Saving..."
              : isEditingFolder
                ? "Update Folder"
                : "Create Folder"}</span
          >
        </button>
      </div>
    </div>
  </div>
{/if}

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
{#if isBulkEditRulesModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <Pencil class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              Bulk Edit {table.selectedCount} Rules
            </h2>
            <p class="text-xs text-slate-400">Apply batch changes to selected compliance rules</p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (isBulkEditRulesModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto p-6 text-xs">
        {#if bulkRulesModalError}
          <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-rose-300">
            {bulkRulesModalError}
          </div>
        {/if}

        <div class="space-y-1.5">
          <label for="bulk-rule-ruleset" class="block font-semibold text-slate-300">
            Move to Ruleset Folder
          </label>
          <select
            id="bulk-rule-ruleset"
            bind:value={bulkRuleRulesetId}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="__keep__">— Keep current folder —</option>
            {#each folders as f (f)}
              <option value={f.ruleset_id}>{f.display_name} ({f.ruleset_id})</option>
            {/each}
          </select>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label for="bulk-rule-category" class="block font-semibold text-slate-300">
              Domain Category
            </label>
            <select
              id="bulk-rule-category"
              bind:value={bulkRuleCategory}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="__keep__">— Keep current —</option>
              <option value="Arch">Arch (Architectural)</option>
              <option value="Piping">Piping (Corrosion)</option>
              <option value="seismic">seismic (Clearance)</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label for="bulk-rule-mechanism" class="block font-semibold text-slate-300">
              Mechanism
            </label>
            <select
              id="bulk-rule-mechanism"
              bind:value={bulkRuleMechanism}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="__keep__">— Keep current —</option>
              <option value="CODE">CODE (Building Code)</option>
              <option value="GC-001">GC-001 (Galvanic)</option>
              <option value="CC-001">CC-001 (Crevice)</option>
              <option value="MC-001">MC-001 (Microbiological)</option>
              <option value="SEISMIC">SEISMIC (Clearance)</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label for="bulk-rule-severity" class="block font-semibold text-slate-300">
              Severity
            </label>
            <select
              id="bulk-rule-severity"
              bind:value={bulkRuleSeverity}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="__keep__">— Keep current —</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label for="bulk-rule-review" class="block font-semibold text-slate-300">
              Review Status
            </label>
            <select
              id="bulk-rule-review"
              bind:value={bulkRuleNeedsReview}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="__keep__">— Keep current —</option>
              <option value="0">Mark as Approved (0)</option>
              <option value="1">Mark as Needs Review (1)</option>
            </select>
          </div>
        </div>
      </div>

      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950 px-6 py-3"
      >
        <button
          type="button"
          onclick={() => (isBulkEditRulesModalOpen = false)}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isBulkUpdatingRules}
          onclick={handleBulkUpdateRules}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          <span>{isBulkUpdatingRules ? "Updating..." : `Update ${table.selectedCount} Rules`}</span>
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Bulk Edit Ruleset Folders Modal -->
{#if isBulkEditFoldersModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <Pencil class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              Bulk Edit {selectedFolderRulesetIds.length} Folders
            </h2>
            <p class="text-xs text-slate-400">Apply batch changes to selected ruleset folders</p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (isBulkEditFoldersModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto p-6 text-xs">
        {#if bulkFoldersModalError}
          <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-rose-300">
            {bulkFoldersModalError}
          </div>
        {/if}

        <div class="space-y-1.5">
          <label for="bulk-folder-category" class="block font-semibold text-slate-300">
            Domain Category
          </label>
          <select
            id="bulk-folder-category"
            bind:value={bulkFolderCategory}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="__keep__">— Keep current —</option>
            <option value="Arch">Arch (Architectural)</option>
            <option value="Piping">Piping (Corrosion)</option>
            <option value="seismic">seismic (Clearance)</option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label for="bulk-folder-mechanism-scope" class="block font-semibold text-slate-300">
            Mechanism Scope
          </label>
          <select
            id="bulk-folder-mechanism-scope"
            bind:value={bulkFolderMechanismScope}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="__keep__">— Keep current —</option>
            <option value="CODE">CODE (Building Code)</option>
            <option value="GC-001">GC-001 (Galvanic)</option>
            <option value="CC-001">CC-001 (Crevice)</option>
            <option value="MC-001">MC-001 (Microbiological)</option>
            <option value="SEISMIC">SEISMIC (Clearance Detection)</option>
          </select>
        </div>
      </div>

      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950 px-6 py-3"
      >
        <button
          type="button"
          onclick={() => (isBulkEditFoldersModalOpen = false)}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isBulkUpdatingFolders}
          onclick={handleBulkUpdateFolders}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          <span
            >{isBulkUpdatingFolders
              ? "Updating..."
              : `Update ${selectedFolderRulesetIds.length} Folders`}</span
          >
        </button>
      </div>
    </div>
  </div>
{/if}

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
{#if isImportIdsModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div
            class="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-2 text-emerald-400"
          >
            <Upload class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">Import Ruleset</h2>
            <p class="text-xs text-slate-400">
              Parse a buildingSMART IDS (.ids/XML) or BIM-Guard JSON ruleset file into new rules
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (isImportIdsModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto p-6 text-xs">
        <RulesetImportForm
          defaultRulesetId={selectedFolderId || ""}
          onCancel={() => (isImportIdsModalOpen = false)}
          onImported={handleIdsImported}
        />
      </div>
    </div>
  </div>
{/if}

<!-- Save Snapshot Modal -->
{#if isSaveSnapshotModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-purple-500/20 bg-purple-500/10 p-2 text-purple-400">
            <Camera class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">Save Rule Snapshot</h2>
            <p class="text-xs text-slate-400">
              Freeze "{selectedFolderId}"'s current rules into a named, downloadable snapshot
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (isSaveSnapshotModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto p-6 text-xs">
        {#if saveSnapshotError}
          <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-rose-300">
            {saveSnapshotError}
          </div>
        {/if}

        <div class="space-y-1.5">
          <label for="snapshot-name" class="block font-semibold text-slate-300">
            Snapshot Name <span class="text-rose-400">*</span>
          </label>
          <input
            id="snapshot-name"
            type="text"
            bind:value={saveSnapshotName}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="space-y-1.5">
          <label for="snapshot-mode" class="block font-semibold text-slate-300">Source Mode</label>
          <select
            id="snapshot-mode"
            bind:value={saveSnapshotSourceMode}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="manual">Manual</option>
            <option value="pdf">PDF Extraction</option>
            <option value="ids">IDS Import</option>
            <option value="mixed">Mixed</option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label for="snapshot-notes" class="block font-semibold text-slate-300">Notes</label>
          <textarea
            id="snapshot-notes"
            rows="3"
            bind:value={saveSnapshotNotes}
            placeholder="Optional context for this configuration..."
            class="w-full resize-y rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          ></textarea>
        </div>
      </div>

      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950 px-6 py-3"
      >
        <button
          type="button"
          onclick={() => (isSaveSnapshotModalOpen = false)}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSavingSnapshot || !saveSnapshotName.trim()}
          onclick={handleSaveSnapshot}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          <span>{isSavingSnapshot ? "Saving..." : "Save Snapshot"}</span>
        </button>
      </div>
    </div>
  </div>
{/if}

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
      class="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div>
          <h2 class="text-base font-bold tracking-tight text-slate-50">{viewingSource.filename}</h2>
          {#if viewingSource.page_number}
            <p class="mt-0.5 text-xs text-slate-400">Page {viewingSource.page_number}</p>
          {/if}
        </div>
        <button
          type="button"
          onclick={() => (viewingSource = null)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
      <div class="flex-1 overflow-hidden">
        <DocumentViewer
          documentId={viewingSource.document_id}
          page={viewingSource.page_number}
          highlightText={viewingSource.snippet}
        />
      </div>
    </div>
  </div>
{/if}

{#if sourceViewError}
  <div class="fixed bottom-6 right-6 z-50 max-w-sm rounded-xl border border-red-800/60 bg-red-950/90 px-4 py-3 text-xs text-red-200 shadow-2xl">
    <div class="flex items-start justify-between gap-3">
      <span>{sourceViewError}</span>
      <button type="button" onclick={() => (sourceViewError = "")} class="shrink-0 text-red-300 hover:text-red-100">
        <X class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
{/if}
