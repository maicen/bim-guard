<script lang="ts">
  import { onMount, onDestroy } from "svelte";
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
  } from "lucide-svelte";
  import { rulesApi, ruleExtractionApi } from "../lib/api";
  import type { Rule, RuleFolder, RulesetCategory, RuleSnapshot, RuleSnapshotSourceMode, IdsImportResult } from "../lib/types";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import RuleForm from "../lib/components/RuleForm.svelte";
  import IdsImportForm from "../lib/components/IdsImportForm.svelte";
  import HoverCard from "../lib/components/HoverCard.svelte";
  import { describeMechanism } from "../lib/glossary";

  // Top-level tab: Rules catalog vs saved Rule Configuration Snapshots
  let activeMainTab: "rules" | "snapshots" = "rules";

  // Snapshots tab state
  let snapshots: RuleSnapshot[] = [];
  let isLoadingSnapshots = false;
  let snapshotsError = "";
  let snapshotSearchQuery = "";
  let snapshotSortField: "name" | "source_ruleset_id" | "category" | "rule_count" | "created_at" = "created_at";
  let snapshotSortAsc = false;
  let snapshotCurrentPage = 1;
  let snapshotPageSize = 10;
  let selectedSnapshotIds: Set<number> = new Set();
  let snapshotToDelete: RuleSnapshot | null = null;
  let isBulkDeleteSnapshotsModalOpen = false;

  // Import IDS modal state
  let isImportIdsModalOpen = false;

  // Save Snapshot modal state
  let isSaveSnapshotModalOpen = false;
  let saveSnapshotName = "";
  let saveSnapshotNotes = "";
  let saveSnapshotSourceMode: RuleSnapshotSourceMode = "manual";
  let isSavingSnapshot = false;
  let saveSnapshotError = "";

  const cachedRules = rulesApi.getCachedList();
  const cachedFolders = rulesApi.getCachedFolders();

  let rules: Rule[] = cachedRules || [];
  let folders: RuleFolder[] = cachedFolders || [];
  let isLoading = !cachedRules;
  let isRefreshing = false;
  let error = "";
  let successMessage = "";
  let isDeleteModalOpen = false;
  let ruleToDelete: { id: number; ruleId: string } | null = null;
  let isViewModalOpen = false;
  let ruleToView: Rule | null = null;
  let unsubscribeRules: (() => void) | null = null;

  // Filter state
  let searchQuery = "";
  let selectedFolderId: string | null = null;
  let selectedMechanism: string = "all";
  let selectedCategory: RulesetCategory | "all" = "all";
  let filterNeedsReview: boolean = false;

  // Rule edit/create modal state
  let isModalOpen = false;
  let editingRule: Rule | null = null;

  // Sensible defaults for a brand-new rule, based on whatever the catalog is
  // currently filtered to — mirrors what the create button implied before.
  let newRuleDefaultRulesetId = "BUILDING-CODE-PART9";
  let newRuleDefaultCategory: RulesetCategory = "Arch";
  $: newRuleDefaultRulesetId =
    selectedFolderId ||
    (selectedCategory !== "all"
      ? folders.find((f) => f.category === selectedCategory)?.ruleset_id
      : undefined) ||
    "BUILDING-CODE-PART9";
  $: newRuleDefaultCategory =
    selectedCategory !== "all"
      ? selectedCategory
      : selectedFolderId
        ? ((folders.find((f) => f.ruleset_id === selectedFolderId)
            ?.category as RulesetCategory) || "Arch")
        : "Arch";

  // Folder Create/Edit Modal State
  let isFolderModalOpen = false;
  let isEditingFolder = false;
  let folderRulesetId = "";
  let folderDisplayName = "";
  let folderDescription = "";
  let folderMechanismScope = "";
  let folderCategory: RulesetCategory = "Arch";
  let folderModalError = "";
  let isSavingFolder = false;

  // Folder Delete Modal State
  let isDeleteFolderModalOpen = false;
  let folderToDelete: RuleFolder | null = null;
  let isDeletingFolder = false;

  // Bulk Rule Modification State
  let isBulkEditRulesModalOpen = false;
  let bulkRuleRulesetId = "__keep__";
  let bulkRuleCategory: RulesetCategory | "__keep__" = "__keep__";
  let bulkRuleMechanism = "__keep__";
  let bulkRuleSeverity = "__keep__";
  let bulkRuleNeedsReview: "0" | "1" | "__keep__" = "__keep__";
  let isBulkUpdatingRules = false;
  let bulkRulesModalError = "";

  // Bulk Folder Selection & Modification State
  let selectedFolderRulesetIds: string[] = [];
  let isFolderSelectionMode = false;
  let isBulkEditFoldersModalOpen = false;
  let bulkFolderCategory: RulesetCategory | "__keep__" = "__keep__";
  let bulkFolderMechanismScope = "__keep__";
  let isBulkUpdatingFolders = false;
  let bulkFoldersModalError = "";
  let isBulkDeleteFoldersModalOpen = false;
  let isBulkDeletingFolders = false;

  // Resizable Sidebar Splitter State
  let sidebarWidth = 280;
  let isDraggingDivider = false;
  let dragStartX = 0;
  let dragStartWidth = 280;

  async function loadData(force = false) {
    if (!rules.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }
    error = "";
    try {
      const [rulesData, foldersData] = await Promise.all([
        rulesApi.list(undefined, { forceRefresh: force }),
        rulesApi.folders(undefined, { forceRefresh: force }),
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
    } catch {}

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

  $: archCount = rules.filter((r) => (r.category || "").toLowerCase() === "arch").length;
  $: pipingCount = rules.filter((r) => (r.category || "").toLowerCase() === "piping").length;
  $: seismicCount = rules.filter((r) => (r.category || "").toLowerCase() === "seismic").length;

  $: filteredFolders = folders.filter((f) => {
    if (selectedCategory === "all") return true;
    return (f.category || "").toLowerCase() === selectedCategory.toLowerCase();
  });

  $: filteredRules = rules.filter((r) => {
    const matchesSearch =
      searchQuery === "" ||
      (r.rule_id || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.description || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (r.property_name || "")
        .toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      (r.compare_property || "")
        .toLowerCase()
        .includes(searchQuery.toLowerCase());

    const matchesFolder =
      !selectedFolderId || r.ruleset_id === selectedFolderId;

    const matchesMechanism =
      selectedMechanism === "all" || r.mechanism === selectedMechanism;

    const matchesCategory =
      selectedCategory === "all" ||
      (r.category || "").toLowerCase() === selectedCategory.toLowerCase();

    const matchesReview = !filterNeedsReview || r.needs_review === 1;

    return matchesSearch && matchesFolder && matchesMechanism && matchesCategory && matchesReview;
  });

  let selectedRuleIds: number[] = [];
  let isBulkDeleteModalOpen = false;

  let currentPage = 1;
  let pageSize = 10;

  $: totalItems = filteredRules.length;
  $: paginatedRules = filteredRules.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  $: allFilteredSelected =
    filteredRules.length > 0 &&
    filteredRules.every((r) => selectedRuleIds.includes(r.id));

  function toggleSelectAll() {
    if (allFilteredSelected) {
      selectedRuleIds = [];
    } else {
      selectedRuleIds = filteredRules.map((r) => r.id);
    }
  }

  function toggleSelectRule(id: number) {
    if (selectedRuleIds.includes(id)) {
      selectedRuleIds = selectedRuleIds.filter((rId) => rId !== id);
    } else {
      selectedRuleIds = [...selectedRuleIds, id];
    }
  }

  // ── Bulk Rules Handlers ───────────────────────────────────────────────────

  function openBulkEditRulesModal() {
    if (!selectedRuleIds.length) return;
    bulkRuleRulesetId = "__keep__";
    bulkRuleCategory = "__keep__";
    bulkRuleMechanism = "__keep__";
    bulkRuleSeverity = "__keep__";
    bulkRuleNeedsReview = "__keep__";
    bulkRulesModalError = "";
    isBulkEditRulesModalOpen = true;
  }

  async function handleBulkUpdateRules() {
    if (!selectedRuleIds.length) return;
    isBulkUpdatingRules = true;
    bulkRulesModalError = "";
    try {
      const payload: any = { rule_ids: selectedRuleIds };
      if (bulkRuleRulesetId !== "__keep__") payload.ruleset_id = bulkRuleRulesetId;
      if (bulkRuleCategory !== "__keep__") payload.category = bulkRuleCategory;
      if (bulkRuleMechanism !== "__keep__") payload.mechanism = bulkRuleMechanism;
      if (bulkRuleSeverity !== "__keep__") payload.severity = bulkRuleSeverity;
      if (bulkRuleNeedsReview !== "__keep__") payload.needs_review = parseInt(bulkRuleNeedsReview, 10);

      const res = await rulesApi.bulkUpdate(payload);
      successMessage = `Successfully updated ${res.success_count} rule(s).`;
      isBulkEditRulesModalOpen = false;
      selectedRuleIds = [];
      await loadData(true);
      setTimeout(() => (successMessage = ""), 4000);
    } catch (err: any) {
      bulkRulesModalError = err.message || "Failed to update rules in bulk.";
    } finally {
      isBulkUpdatingRules = false;
    }
  }

  async function confirmBulkDelete() {
    if (!selectedRuleIds.length) return;
    try {
      const res = await rulesApi.bulkDelete(selectedRuleIds);
      rules = rules.filter((r) => !selectedRuleIds.includes(r.id));
      selectedRuleIds = [];
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
      if (bulkFolderMechanismScope !== "__keep__") payload.mechanism_scope = bulkFolderMechanismScope;

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

  $: {
    searchQuery;
    selectedFolderId;
    selectedMechanism;
    selectedCategory;
    filterNeedsReview;
    currentPage = 1;
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
    successMessage = `Imported ${res.created_count} of ${res.total_parsed} rules from IDS file into "${res.ruleset_id}".`;
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
        selectedSnapshotIds.delete(id);
        selectedSnapshotIds = selectedSnapshotIds;
      })
      .catch((err: any) => {
        snapshotsError = err.message || "Failed to delete snapshot.";
      })
      .finally(() => {
        snapshotToDelete = null;
      });
  }

  async function confirmBulkDeleteSnapshots() {
    const ids = Array.from(selectedSnapshotIds);
    for (const id of ids) {
      try {
        await rulesApi.deleteSnapshot(id);
      } catch (err: any) {
        snapshotsError = err.message || `Failed to delete snapshot ${id}.`;
      }
    }
    snapshots = snapshots.filter((s) => !selectedSnapshotIds.has(s.id));
    selectedSnapshotIds = new Set();
    isBulkDeleteSnapshotsModalOpen = false;
  }

  function toggleSnapshotSelection(id: number) {
    if (selectedSnapshotIds.has(id)) {
      selectedSnapshotIds.delete(id);
    } else {
      selectedSnapshotIds.add(id);
    }
    selectedSnapshotIds = selectedSnapshotIds;
  }

  function toggleAllSnapshotsSelection() {
    if (selectedSnapshotIds.size === paginatedSnapshots.length && paginatedSnapshots.length > 0) {
      selectedSnapshotIds = new Set();
    } else {
      selectedSnapshotIds = new Set(paginatedSnapshots.map((s) => s.id));
    }
  }

  function handleSnapshotSort(col: string) {
    if (snapshotSortField === col) {
      snapshotSortAsc = !snapshotSortAsc;
    } else {
      snapshotSortField = col as typeof snapshotSortField;
      snapshotSortAsc = true;
    }
  }

  $: filteredSnapshots = snapshots.filter((s) => {
    if (!snapshotSearchQuery.trim()) return true;
    const q = snapshotSearchQuery.toLowerCase();
    return (
      s.name.toLowerCase().includes(q) ||
      s.source_ruleset_id.toLowerCase().includes(q) ||
      (s.notes || "").toLowerCase().includes(q)
    );
  });

  $: sortedSnapshots = [...filteredSnapshots].sort((a, b) => {
    const av = a[snapshotSortField];
    const bv = b[snapshotSortField];
    const cmp = typeof av === "number" && typeof bv === "number"
      ? av - bv
      : String(av ?? "").localeCompare(String(bv ?? ""));
    return snapshotSortAsc ? cmp : -cmp;
  });

  $: snapshotTotalPages = Math.max(1, Math.ceil(sortedSnapshots.length / snapshotPageSize));
  $: paginatedSnapshots = sortedSnapshots.slice(
    (snapshotCurrentPage - 1) * snapshotPageSize,
    snapshotCurrentPage * snapshotPageSize,
  );

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
      } catch {}
    }
  }

  function handleDividerKeyDown(event: KeyboardEvent) {
    if (event.key === "ArrowLeft") {
      sidebarWidth = Math.max(sidebarWidth - 16, 180);
      try { localStorage.setItem("bimguard_rules_sidebar_width", String(sidebarWidth)); } catch {}
    } else if (event.key === "ArrowRight") {
      sidebarWidth = Math.min(sidebarWidth + 16, 550);
      try { localStorage.setItem("bimguard_rules_sidebar_width", String(sidebarWidth)); } catch {}
    }
  }
</script>

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div
        class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
      >
        Library
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        Rules Catalog
      </h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Engineering criteria for corrosion, seismic clearance, and architectural
        building codes.
      </p>
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        on:click={() => loadData(true)}
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-900/60 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 transition-colors"
        title="Refresh rules catalog"
      >
        <RotateCw class="w-3.5 h-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
        <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
      </button>

      <button
        type="button"
        on:click={handleSeedRules}
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-colors"
        title="Seed engine rulesets: GC-001, CC-001, MC-001"
      >
        <Database class="w-3.5 h-3.5 text-emerald-400" />
        <span>Seed Engines</span>
      </button>

      {#if activeMainTab === "rules"}
        <button
          type="button"
          on:click={openImportIdsModal}
          class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-colors"
          title="Import rules from a buildingSMART IDS file"
        >
          <Upload class="w-3.5 h-3.5 text-emerald-400" />
          <span>Import IDS</span>
        </button>

        {#if selectedFolderId}
          <a
            href={ruleExtractionApi.getIdsExportUrl(selectedFolderId)}
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-colors"
            title="Export current ruleset into buildingSMART IDS XML"
          >
            <Download class="w-3.5 h-3.5 text-blue-400" />
            <span>Export IDS</span>
          </a>

          <button
            type="button"
            on:click={openSaveSnapshotModal}
            class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 transition-colors"
            title="Save the current folder's rules as a reusable snapshot"
          >
            <Camera class="w-3.5 h-3.5 text-purple-400" />
            <span>Save Snapshot</span>
          </button>
        {/if}

        <button
          type="button"
          on:click={openCreateModal}
          class="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>New Rule</span>
        </button>
      {/if}
    </div>
  </div>

  {#if error}
    <div
      class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs"
    >
      {error}
    </div>
  {/if}

  {#if successMessage}
    <div
      class="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2"
    >
      <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Main Tab Toggle: Rules Catalog vs Saved Snapshots -->
  <div class="flex items-center gap-2 p-1.5 rounded-2xl bg-slate-900/60 border border-slate-800 w-fit">
    <button
      type="button"
      on:click={() => switchMainTab("rules")}
      class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all {activeMainTab === 'rules'
        ? 'bg-[#0071e3] text-white shadow-sm'
        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
    >
      <ListChecks class="w-3.5 h-3.5" />
      <span>Rules Catalog</span>
    </button>
    <button
      type="button"
      on:click={() => switchMainTab("snapshots")}
      class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all {activeMainTab === 'snapshots'
        ? 'bg-[#0071e3] text-white shadow-sm'
        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
    >
      <Camera class="w-3.5 h-3.5" />
      <span>Snapshots</span>
      {#if snapshots.length > 0}
        <span class="text-[10px] opacity-75 ml-0.5">({snapshots.length})</span>
      {/if}
    </button>
  </div>

  {#if activeMainTab === "rules"}
  <!-- Category Selector Tabs: Arch | Piping | seismic -->
  <div class="flex items-center gap-2 p-1.5 rounded-2xl bg-slate-900/60 border border-slate-800 w-fit">
    <button
      type="button"
      on:click={() => {
        selectedCategory = "all";
        selectedFolderId = null;
      }}
      class="px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all {selectedCategory === 'all'
        ? 'bg-[#0071e3] text-white shadow-sm'
        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
    >
      All Categories
    </button>
    <button
      type="button"
      on:click={() => {
        selectedCategory = "Arch";
        selectedFolderId = null;
      }}
      class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all {selectedCategory === 'Arch'
        ? 'bg-blue-600 text-white shadow-sm'
        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
    >
      <span class="w-2 h-2 rounded-full bg-blue-400"></span>
      <span>Arch</span>
      <span class="text-[10px] opacity-75 ml-0.5">({archCount})</span>
    </button>
    <button
      type="button"
      on:click={() => {
        selectedCategory = "Piping";
        selectedFolderId = null;
      }}
      class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all {selectedCategory === 'Piping'
        ? 'bg-amber-600 text-white shadow-sm'
        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
    >
      <span class="w-2 h-2 rounded-full bg-amber-400"></span>
      <span>Piping</span>
      <span class="text-[10px] opacity-75 ml-0.5">({pipingCount})</span>
    </button>
    <button
      type="button"
      on:click={() => {
        selectedCategory = "seismic";
        selectedFolderId = null;
      }}
      class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all {selectedCategory === 'seismic'
        ? 'bg-purple-600 text-white shadow-sm'
        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
    >
      <span class="w-2 h-2 rounded-full bg-purple-400"></span>
      <span>seismic</span>
      <span class="text-[10px] opacity-75 ml-0.5">({seismicCount})</span>
    </button>
  </div>

  <!-- Main Layout: Resizable Split View (Folders Sidebar + Draggable Divider + Rules Table) -->
  <div class="flex flex-col md:flex-row gap-0 items-stretch relative">
    <!-- Folder tree sidebar -->
    <div
      class="p-4 rounded-2xl md:rounded-r-none bg-slate-900/60 border border-slate-800 space-y-3 shrink-0 flex flex-col w-full md:w-auto"
      style="width: 100%; max-width: 100%;"
      style:width={typeof window !== 'undefined' && window.innerWidth >= 768 ? `${sidebarWidth}px` : '100%'}
    >
      <div class="flex items-center justify-between px-1">
        <div class="flex items-center gap-1.5">
          <div
            class="text-xs font-bold uppercase tracking-wider text-slate-400"
          >
            Ruleset Folders
          </div>
          {#if folders.length > 0}
            <button
              type="button"
              on:click={toggleFolderSelectionMode}
              class="p-1 rounded-md transition-colors {isFolderSelectionMode || selectedFolderRulesetIds.length > 0
                ? 'text-blue-400 bg-blue-500/10'
                : 'text-slate-500 hover:text-white hover:bg-slate-800'}"
              title={isFolderSelectionMode ? 'Exit folder select mode' : 'Select multiple folders'}
            >
              <CheckSquare class="w-3.5 h-3.5" />
            </button>
          {/if}
        </div>
        <button
          type="button"
          on:click={openCreateFolderModal}
          class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-blue-600 transition-colors border border-slate-700/60"
          title="Create New Ruleset Folder"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>Folder</span>
        </button>
      </div>

      <!-- Folder Bulk Action Bar when folders are selected -->
      {#if selectedFolderRulesetIds.length > 0}
        <div
          class="p-2 rounded-xl bg-blue-950/90 border border-blue-800 text-xs text-blue-200 flex items-center justify-between gap-1 shadow-md animate-in fade-in duration-150"
        >
          <div class="flex items-center gap-1 font-medium text-[11px] truncate">
            <span class="font-bold text-white">{selectedFolderRulesetIds.length}</span>
            <span class="truncate">selected</span>
          </div>
          <div class="flex items-center gap-1">
            <button
              type="button"
              on:click={openBulkEditFoldersModal}
              class="px-2 py-1 rounded-md bg-blue-600/40 hover:bg-blue-600 text-white font-medium text-[10px] transition-colors"
              title="Bulk edit selected folders"
            >
              Edit
            </button>
            <button
              type="button"
              on:click={() => (isBulkDeleteFoldersModalOpen = true)}
              class="px-2 py-1 rounded-md bg-rose-600/40 hover:bg-rose-600 text-white font-medium text-[10px] transition-colors"
              title="Bulk delete selected folders"
            >
              Delete
            </button>
            <button
              type="button"
              on:click={() => (selectedFolderRulesetIds = [])}
              class="p-1 rounded-md hover:bg-blue-900/60 text-blue-300 hover:text-white"
              title="Clear selection"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      {/if}

      <div class="space-y-1 overflow-y-auto max-h-[70vh] flex-1 pr-1">
        <button
          type="button"
          on:click={() => (selectedFolderId = null)}
          class="w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium transition-colors {!selectedFolderId
            ? 'bg-[#0071e3] text-white shadow-sm'
            : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
        >
          <div class="flex items-center gap-2">
            <FolderOpen class="w-3.5 h-3.5" />
            <span>All Rules</span>
          </div>
          <span class="text-[10px] opacity-75">{rules.length}</span>
        </button>

        {#each filteredFolders as folder}
          <div
            class="group/folder relative flex items-center justify-between rounded-xl text-xs font-medium transition-colors {selectedFolderId ===
            folder.ruleset_id
              ? 'bg-[#0071e3] text-white shadow-sm'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'}"
          >
            {#if isFolderSelectionMode || selectedFolderRulesetIds.length > 0}
              <button
                type="button"
                class="pl-2.5 py-2 cursor-pointer flex items-center shrink-0 bg-transparent border-0"
                on:click|stopPropagation={(e) => toggleSelectFolder(folder.ruleset_id, e)}
                title="Select folder"
              >
                <input
                  type="checkbox"
                  checked={selectedFolderRulesetIds.includes(folder.ruleset_id)}
                  tabindex="-1"
                  class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-3.5 h-3.5 pointer-events-none"
                />
              </button>
            {/if}

            <button
              type="button"
              on:click={() => (selectedFolderId = folder.ruleset_id)}
              class="flex items-center gap-2 truncate flex-1 min-w-0 {isFolderSelectionMode || selectedFolderRulesetIds.length > 0 ? 'px-1.5' : 'px-2.5'} py-2 text-left"
              title="{folder.display_name} ({folder.ruleset_id})"
            >
              <Folder class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">{folder.display_name}</span>
            </button>

            <div class="flex items-center gap-1 shrink-0 pr-2">
              {#if folder.category}
                <span
                  class="text-[9px] px-1.5 py-0.5 rounded font-mono font-medium {selectedFolderId === folder.ruleset_id
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
              <div class="hidden group-hover/folder:flex items-center gap-0.5 ml-1">
                <button
                  type="button"
                  on:click={(e) => openEditFolderModal(folder, e)}
                  class="p-1 rounded hover:bg-black/30 text-white/80 hover:text-white transition-colors"
                  title="Edit Folder"
                >
                  <Pencil class="w-3 h-3" />
                </button>
                <button
                  type="button"
                  on:click={(e) => promptDeleteFolder(folder, e)}
                  class="p-1 rounded hover:bg-rose-500/30 text-rose-300 hover:text-rose-200 transition-colors"
                  title="Delete Folder"
                >
                  <Trash2 class="w-3 h-3" />
                </button>
              </div>

              <span class="text-[10px] opacity-75 group-hover/folder:hidden ml-1">
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
      on:pointerdown={handleDividerPointerDown}
      on:pointermove={handleDividerPointerMove}
      on:pointerup={handleDividerPointerUp}
      on:pointercancel={handleDividerPointerUp}
      on:keydown={handleDividerKeyDown}
      class="hidden md:flex items-center justify-center w-3 -mx-1.5 cursor-col-resize z-20 group relative focus:outline-none transition-colors select-none"
      title="Drag to resize Ruleset Folders sidebar (or use Left/Right Arrow keys)"
    >
      <div
        class="w-1 h-full rounded-full transition-all duration-150 {isDraggingDivider
          ? 'bg-[#0071e3] shadow-[0_0_10px_rgba(0,113,227,0.9)] w-1.5'
          : 'bg-slate-800 group-hover:bg-[#0071e3]/80'}"
      ></div>
      <!-- Grip handle indicator in the middle -->
      <div
        class="absolute top-1/2 -translate-y-1/2 w-4 h-7 rounded-md border border-slate-700 bg-slate-900 flex items-center justify-center pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity shadow-lg {isDraggingDivider
          ? '!opacity-100 border-[#0071e3] bg-[#0071e3]'
          : ''}"
      >
        <GripVertical class="w-3 h-3 text-slate-400 {isDraggingDivider ? 'text-white' : ''}" />
      </div>
    </div>

    <!-- Rules Table Area -->
    <div class="flex-1 min-w-0 md:pl-4 space-y-4 pt-4 md:pt-0">
      <!-- Search & Filters -->
      <div
        class="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col sm:flex-row items-center gap-3"
      >
        <div class="relative flex-1 w-full">
          <Search
            class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2"
          />
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="Search rules by ID, description, property..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <select
          bind:value={selectedMechanism}
          class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          <option value="all">All Mechanisms</option>
          <option value="CODE">Building Code</option>
          <option value="GC-001">Galvanic (GC-001)</option>
          <option value="CC-001">Crevice (CC-001)</option>
          <option value="MC-001">Microbiological (MC-001)</option>
          <option value="SEISMIC">Seismic Clearance</option>
        </select>

        <label
          class="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer whitespace-nowrap"
        >
          <input
            type="checkbox"
            bind:checked={filterNeedsReview}
            class="rounded border-slate-700 bg-slate-950 text-[#0071e3]"
          />
          <span>Needs Review</span>
        </label>
      </div>

      <!-- Bulk Operations Bar -->
      <BulkActionBar
        selectedCount={selectedRuleIds.length}
        itemLabel="rule"
        onClearSelection={() => (selectedRuleIds = [])}
        onBulkEdit={openBulkEditRulesModal}
        onBulkDelete={() => (isBulkDeleteModalOpen = true)}
      />

      <!-- Table Container -->
      <div
        class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40"
      >
        {#if isLoading}
          <div class="p-12 text-center text-xs text-slate-400">
            Loading compliance rules...
          </div>
        {:else if filteredRules.length === 0}
          <div class="p-12 text-center text-xs text-slate-500 space-y-2">
            <p>No rules found for this folder or filter criteria.</p>
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
              <thead
                class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
              >
                <tr>
                  <th class="py-3 px-4 w-10">
                    <input
                      type="checkbox"
                      checked={allFilteredSelected}
                      on:change={toggleSelectAll}
                      class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-4 h-4"
                      title="Select or deselect all visible rules"
                    />
                  </th>
                  <th class="py-3 px-4">Rule Ref</th>
                  <th class="py-3 px-4">Category</th>
                  <th class="py-3 px-4">Mechanism</th>
                  <th class="py-3 px-4">Target Property</th>
                  <th class="py-3 px-4">Condition</th>
                  <th class="py-3 px-4">Severity</th>
                  <th class="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each paginatedRules as rule}
                  {@const mech = describeMechanism(rule.mechanism || "CODE")}
                  <tr class="hover:bg-slate-900/60 transition-colors {selectedRuleIds.includes(rule.id) ? 'bg-blue-950/20' : ''}">
                    <td class="py-3 px-4 w-10">
                      <input
                        type="checkbox"
                        checked={selectedRuleIds.includes(rule.id)}
                        on:change={() => toggleSelectRule(rule.id)}
                        class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-4 h-4"
                      />
                    </td>
                    <td class="py-3 px-4">
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
                        showFooter={!!rule.source_text}
                      >
                        <span slot="trigger" class="block min-w-0 cursor-help text-left">
                          <span class="block font-mono font-bold text-slate-100">
                            {rule.rule_id || `Rule #${rule.id}`}
                          </span>
                          <span class="block text-[11px] text-slate-400 truncate max-w-xs">
                            {rule.description || "No description"}
                          </span>
                        </span>

                        <div class="space-y-2">
                          <p>{rule.description || "This rule carries no description."}</p>

                          <dl class="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-[10px]">
                            <dt class="text-slate-500 uppercase tracking-wider">Checks</dt>
                            <dd class="font-mono text-slate-200 break-words">
                              {rule.property_set || "Pset_Compliance"}.{rule.property_name || "-"}
                            </dd>
                            <dt class="text-slate-500 uppercase tracking-wider">Category</dt>
                            <dd class="font-mono text-slate-200 break-words">
                              {rule.rule_category || rule.category || "-"}
                            </dd>
                            <dt class="text-slate-500 uppercase tracking-wider">Severity</dt>
                            <dd class="font-mono text-slate-200">{rule.severity || "-"}</dd>
                          </dl>

                          {#if rule.needs_review}
                            <p class="text-[10px] text-amber-400">
                              Extracted automatically and not yet confirmed by a reviewer.
                            </p>
                          {/if}
                        </div>

                        <span slot="footer" class="break-words italic">
                          “{rule.source_text}”
                        </span>
                      </HoverCard>
                    </td>
                    <td class="py-3 px-4">
                      <span
                        class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold font-mono {rule.category === 'Piping'
                          ? 'bg-amber-950/60 border border-amber-800/50 text-amber-300'
                          : rule.category === 'seismic'
                          ? 'bg-purple-950/60 border border-purple-800/50 text-purple-300'
                          : 'bg-blue-950/60 border border-blue-800/50 text-blue-300'}"
                      >
                        {rule.category || "Arch"}
                      </span>
                    </td>
                    <td class="py-3 px-4">
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
                          <span
                            slot="trigger"
                            class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 font-mono cursor-help"
                          >
                            {rule.mechanism || "CODE"}
                          </span>

                          {mech.description}

                          <span slot="footer" class="font-mono">{mech.reference}</span>
                        </HoverCard>
                      {:else}
                        <span
                          class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 font-mono"
                        >
                          {rule.mechanism || "CODE"}
                        </span>
                      {/if}
                    </td>
                    <td class="py-3 px-4 text-slate-300 font-mono text-[11px]">
                      <div>{rule.property_name || "-"}</div>
                      <div class="text-[10px] text-slate-500">
                        {rule.property_set || "Pset_Compliance"}
                      </div>
                    </td>
                    <td class="py-3 px-4 font-mono text-cyan-300">
                      {#if rule.operator === "field_consistency"}
                        <div class="flex flex-col gap-0.5">
                          <span class="text-[11px] text-amber-300"
                            >≡ {rule.compare_property || "same element"}</span
                          >
                          {#if rule.name_pattern}
                            <span class="text-[10px] text-slate-500 font-sans"
                              >pattern: {rule.name_pattern}</span
                            >
                          {/if}
                        </div>
                      {:else if rule.operator === "unique_within_scope"}
                        <div class="text-[11px] text-purple-300">
                          <span
                            >unique ({rule.uniqueness_scope ||
                              "building"})</span
                          >
                        </div>
                      {:else if rule.value_min_property || rule.value_max_property}
                        <div class="text-[11px] text-emerald-300">
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
                          class="inline-block mt-1 px-1.5 py-0.2 rounded text-[9px] font-sans font-medium bg-amber-950/70 border border-amber-800 text-amber-400"
                        >
                          Needs Review
                        </span>
                      {/if}
                    </td>
                    <td class="py-3 px-4">
                      <span
                        class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold {rule.severity ===
                          'Critical' || rule.severity === 'mandatory'
                          ? 'bg-red-950/60 text-red-400 border border-red-800/60'
                          : rule.severity === 'High'
                            ? 'bg-orange-950/60 text-orange-400 border border-orange-800/60'
                            : 'bg-yellow-950/60 text-yellow-400 border border-yellow-800/60'}"
                      >
                        {rule.severity}
                      </span>
                    </td>
                    <td class="py-3 px-4 text-right whitespace-nowrap">
                      <div class="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          on:click={() => openViewModal(rule)}
                          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                          title="View rule specifications"
                        >
                          <Eye class="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          on:click={() => openEditModal(rule)}
                          class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                          title="Edit rule"
                        >
                          <Edit3 class="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          on:click={() =>
                            promptDelete(rule.id, rule.rule_id || "")}
                          class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                          title="Delete rule"
                        >
                          <Trash2 class="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <TablePagination
            {currentPage}
            {pageSize}
            totalItems={totalItems}
            onPageChange={(p) => (currentPage = p)}
            onPageSizeChange={(s) => {
              pageSize = s;
              currentPage = 1;
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
      <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
        {snapshotsError}
      </div>
    {/if}

    <div class="flex flex-col md:flex-row items-center gap-3">
      <div class="relative flex-1 w-full">
        <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          bind:value={snapshotSearchQuery}
          placeholder="Search snapshots by name, source folder, or notes..."
          class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
        />
      </div>
    </div>

    <BulkActionBar
      selectedCount={selectedSnapshotIds.size}
      itemLabel="snapshot"
      onClearSelection={() => (selectedSnapshotIds = new Set())}
      onBulkDelete={() => (isBulkDeleteSnapshotsModalOpen = true)}
    />

    {#if isLoadingSnapshots}
      <LoadingState message="Loading snapshots..." />
    {:else if sortedSnapshots.length === 0}
      <EmptyState
        title="No snapshots saved yet"
        description="Save a rule folder's current configuration as a named snapshot to download it as a structured PDF later, or to keep a durable record independent of future edits."
        icon={Camera}
      />
    {:else}
      <div class="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-x-auto">
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-slate-800">
              <th class="py-3 px-4 w-10">
                <TableCheckbox
                  checked={selectedSnapshotIds.size === paginatedSnapshots.length && paginatedSnapshots.length > 0}
                  indeterminate={selectedSnapshotIds.size > 0 && selectedSnapshotIds.size < paginatedSnapshots.length}
                  on:change={toggleAllSnapshotsSelection}
                  ariaLabel="Select all snapshots"
                />
              </th>
              <SortHeader column="name" sortField={snapshotSortField} sortAsc={snapshotSortAsc} onSort={handleSnapshotSort}>Name</SortHeader>
              <SortHeader column="source_ruleset_id" sortField={snapshotSortField} sortAsc={snapshotSortAsc} onSort={handleSnapshotSort}>Source Folder</SortHeader>
              <th class="py-3 px-4 text-left text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Mode</th>
              <SortHeader column="category" sortField={snapshotSortField} sortAsc={snapshotSortAsc} onSort={handleSnapshotSort}>Category</SortHeader>
              <SortHeader column="rule_count" sortField={snapshotSortField} sortAsc={snapshotSortAsc} onSort={handleSnapshotSort} align="center">Rules</SortHeader>
              <SortHeader column="created_at" sortField={snapshotSortField} sortAsc={snapshotSortAsc} onSort={handleSnapshotSort}>Saved</SortHeader>
              <th class="py-3 px-4 text-right text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each paginatedSnapshots as snap (snap.id)}
              <tr class="border-b border-slate-800/60 hover:bg-slate-800/30 transition-colors">
                <td class="py-3 px-4">
                  <TableCheckbox
                    checked={selectedSnapshotIds.has(snap.id)}
                    on:change={() => toggleSnapshotSelection(snap.id)}
                    ariaLabel={`Select snapshot ${snap.name}`}
                  />
                </td>
                <td class="py-3 px-4 text-white font-medium">{snap.name}</td>
                <td class="py-3 px-4 text-slate-400 font-mono">{snap.source_ruleset_id}</td>
                <td class="py-3 px-4">
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700 uppercase">
                    {snap.source_mode}
                  </span>
                </td>
                <td class="py-3 px-4 text-slate-400">{snap.category}</td>
                <td class="py-3 px-4 text-center text-slate-300">{snap.rule_count}</td>
                <td class="py-3 px-4 text-slate-400">{snap.created_at ? new Date(snap.created_at).toLocaleString() : "—"}</td>
                <td class="py-3 px-4">
                  <div class="flex items-center justify-end gap-1">
                    <a
                      href={rulesApi.getSnapshotPdfUrl(snap.id)}
                      class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                      title="Download PDF"
                    >
                      <FileText class="w-3.5 h-3.5" />
                    </a>
                    <button
                      type="button"
                      on:click={() => (snapshotToDelete = snap)}
                      class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                      title="Delete snapshot"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <TablePagination
        currentPage={snapshotCurrentPage}
        pageSize={snapshotPageSize}
        totalItems={sortedSnapshots.length}
        onPageChange={(p) => (snapshotCurrentPage = p)}
        onPageSizeChange={(s) => {
          snapshotPageSize = s;
          snapshotCurrentPage = 1;
        }}
      />
    {/if}
  </div>
  {/if}
</div>

<!-- Rule Edit/Create Modal -->
{#if isModalOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
  >
    <div
      class="bg-slate-900 border border-slate-800 w-full max-w-2xl rounded-2xl shadow-2xl p-6 space-y-4 max-h-[90vh] flex flex-col"
    >
      <div
        class="flex items-center justify-between border-b border-slate-800 pb-3"
      >
        <h2 class="text-base font-bold text-white">
          {editingRule ? "Edit Rule" : "Create New Rule"}
        </h2>
        <button
          type="button"
          on:click={() => (isModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="overflow-y-auto pr-1 flex-1">
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
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <ListChecks class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white font-mono">{ruleToView.rule_id || `Rule #${ruleToView.id}`}</h2>
            <p class="text-xs text-slate-400">Rule Specification &amp; Conditions</p>
          </div>
        </div>
        <button
          type="button"
          on:click={() => (isViewModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="p-6 space-y-4 overflow-y-auto text-xs">
        <div>
          <span class="text-slate-400 font-semibold block mb-1">Description</span>
          <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-slate-200">
            {ruleToView.description || 'No description provided.'}
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div class="p-2.5 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">Category</span>
            <span class="font-mono text-white font-semibold">{ruleToView.category || 'Arch'}</span>
          </div>

          <div class="p-2.5 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">Mechanism</span>
            <span class="font-mono text-white font-semibold">{ruleToView.mechanism || 'CODE'}</span>
          </div>

          <div class="p-2.5 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">Severity</span>
            <span class="font-semibold text-amber-400">{ruleToView.severity}</span>
          </div>

          <div class="p-2.5 bg-slate-950/40 rounded-xl border border-slate-800">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">Ruleset / Folder</span>
            <span class="font-mono text-slate-300 truncate block">{ruleToView.ruleset_id || 'Global'}</span>
          </div>
        </div>

        <div class="p-3.5 bg-slate-950/70 rounded-xl border border-slate-800 space-y-2">
          <span class="text-[10px] text-slate-400 uppercase tracking-wider font-semibold block">Target &amp; Condition</span>
          <div class="grid grid-cols-2 gap-2 text-[11px] font-mono">
            <div><span class="text-slate-500">Pset:</span> <span class="text-slate-300">{ruleToView.property_set || 'Pset_Compliance'}</span></div>
            <div><span class="text-slate-500">Property:</span> <span class="text-slate-300">{ruleToView.property_name || '—'}</span></div>
            <div><span class="text-slate-500">Operator:</span> <span class="text-cyan-300">{ruleToView.operator || '=='}</span></div>
            <div><span class="text-slate-500">Target Value:</span> <span class="text-emerald-300">{ruleToView.check_value || (ruleToView.value_min ? `[${ruleToView.value_min}..${ruleToView.value_max}]` : '—')} {ruleToView.unit || ''}</span></div>
          </div>
          {#if ruleToView.compare_property}
            <div class="text-[11px] font-mono text-amber-300 pt-1">
              Compare with: {ruleToView.compare_property}
            </div>
          {/if}
        </div>

        <div>
          <span class="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1">Raw JSON Definition</span>
          <pre class="p-3 bg-slate-950 border border-slate-800 rounded-xl text-slate-400 font-mono text-[11px] overflow-auto max-h-40">{JSON.stringify(ruleToView, null, 2)}</pre>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <button
          type="button"
          on:click={() => {
            isViewModalOpen = false;
            if (ruleToView) openEditModal(ruleToView);
          }}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-white transition-colors"
        >
          <Edit3 class="w-3.5 h-3.5" />
          <span>Edit this Rule</span>
        </button>

        <button
          type="button"
          on:click={() => (isViewModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors"
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
  message={`Are you sure you want to delete ${selectedRuleIds.length} selected compliance rule(s)? This action cannot be undone.`}
  confirmText="Delete Selected Rules"
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => (selectedRuleIds = [])}
/>

<!-- Create / Edit Ruleset Folder Modal -->
{#if isFolderModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            {#if isEditingFolder}
              <Pencil class="w-5 h-5" />
            {:else}
              <Folder class="w-5 h-5" />
            {/if}
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">
              {isEditingFolder ? `Edit Folder: ${folderRulesetId}` : "Create Ruleset Folder"}
            </h2>
            <p class="text-xs text-slate-400">
              {isEditingFolder ? "Update folder name, category, and scope" : "Organize compliance rules under a new domain ruleset"}
            </p>
          </div>
        </div>
        <button
          type="button"
          on:click={() => (isFolderModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
        {#if folderModalError}
          <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300">
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3] font-mono disabled:opacity-60 disabled:cursor-not-allowed"
          />
          {#if !isEditingFolder}
            <p class="text-[11px] text-slate-500">
              Unique ID used to link member rules (e.g. OBC-2024-STAIRS, GC-001, SEISMIC-CLEARANCE).
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
            placeholder="e.g. OBC Part 3 - Fire Protection & Safety"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
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
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
          <label for="folder-desc" class="block font-semibold text-slate-300">
            Description
          </label>
          <textarea
            id="folder-desc"
            rows="3"
            bind:value={folderDescription}
            placeholder="Regulatory standard, scope notes, or compliance criteria..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3] resize-y"
          ></textarea>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-end gap-2">
        <button
          type="button"
          on:click={() => (isFolderModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSavingFolder || !folderRulesetId.trim()}
          on:click={handleSaveFolder}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all disabled:opacity-50"
        >
          <span>{isSavingFolder ? "Saving..." : isEditingFolder ? "Update Folder" : "Create Folder"}</span>
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
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Pencil class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">
              Bulk Edit {selectedRuleIds.length} Rules
            </h2>
            <p class="text-xs text-slate-400">Apply batch changes to selected compliance rules</p>
          </div>
        </div>
        <button
          type="button"
          on:click={() => (isBulkEditRulesModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
        {#if bulkRulesModalError}
          <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300">
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          >
            <option value="__keep__">— Keep current folder —</option>
            {#each folders as f}
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
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="__keep__">— Keep current —</option>
              <option value="0">Mark as Approved (0)</option>
              <option value="1">Mark as Needs Review (1)</option>
            </select>
          </div>
        </div>
      </div>

      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-end gap-2">
        <button
          type="button"
          on:click={() => (isBulkEditRulesModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isBulkUpdatingRules}
          on:click={handleBulkUpdateRules}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all disabled:opacity-50"
        >
          <span>{isBulkUpdatingRules ? "Updating..." : `Update ${selectedRuleIds.length} Rules`}</span>
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Bulk Edit Ruleset Folders Modal -->
{#if isBulkEditFoldersModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Pencil class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">
              Bulk Edit {selectedFolderRulesetIds.length} Folders
            </h2>
            <p class="text-xs text-slate-400">Apply batch changes to selected ruleset folders</p>
          </div>
        </div>
        <button
          type="button"
          on:click={() => (isBulkEditFoldersModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
        {#if bulkFoldersModalError}
          <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300">
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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

      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-end gap-2">
        <button
          type="button"
          on:click={() => (isBulkEditFoldersModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isBulkUpdatingFolders}
          on:click={handleBulkUpdateFolders}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all disabled:opacity-50"
        >
          <span>{isBulkUpdatingFolders ? "Updating..." : `Update ${selectedFolderRulesetIds.length} Folders`}</span>
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
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Upload class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">Import IDS File</h2>
            <p class="text-xs text-slate-400">Parse a buildingSMART IDS (.ids/XML) file into new rules</p>
          </div>
        </div>
        <button
          type="button"
          on:click={() => (isImportIdsModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 overflow-y-auto flex-1 text-xs">
        <IdsImportForm
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
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Camera class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">Save Rule Snapshot</h2>
            <p class="text-xs text-slate-400">
              Freeze "{selectedFolderId}"'s current rules into a named, downloadable snapshot
            </p>
          </div>
        </div>
        <button
          type="button"
          on:click={() => (isSaveSnapshotModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
        {#if saveSnapshotError}
          <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300">
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <div class="space-y-1.5">
          <label for="snapshot-mode" class="block font-semibold text-slate-300">Source Mode</label>
          <select
            id="snapshot-mode"
            bind:value={saveSnapshotSourceMode}
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3] resize-y"
          ></textarea>
        </div>
      </div>

      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-end gap-2">
        <button
          type="button"
          on:click={() => (isSaveSnapshotModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSavingSnapshot || !saveSnapshotName.trim()}
          on:click={handleSaveSnapshot}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all disabled:opacity-50"
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
  message={`Are you sure you want to delete ${selectedSnapshotIds.size} selected snapshot(s)? This cannot be undone.`}
  confirmText="Delete Snapshots"
  danger={true}
  onConfirm={confirmBulkDeleteSnapshots}
  onCancel={() => (isBulkDeleteSnapshotsModalOpen = false)}
/>
