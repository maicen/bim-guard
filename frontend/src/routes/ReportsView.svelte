<script lang="ts">
  import { onMount, untrack } from "svelte";
  import {
    FileText,
    Download,
    CheckCircle2,
    AlertTriangle,
    Clock,
    DollarSign,
    ScanEye,
    RefreshCw,
    FolderArchive,
    Shield,
    Tag,
    Layers,
    MessageSquare,
    Camera,
    Plus,
    Pencil,
    Trash2,
    Eye,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Search,
  } from "lucide-svelte";
  import { projectsApi, analyzeApi, bcfApi, rulesApi } from "../lib/api";
  import type { Project, AnalysisResult, BcfArtifact, BCFTopicResponse } from "../lib/types";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import BcfTopicEditModal from "../lib/components/BcfTopicEditModal.svelte";
  import BcfTopicDetailsModal from "../lib/components/BcfTopicDetailsModal.svelte";
  import BcfBulkEditModal from "../lib/components/BcfBulkEditModal.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import IsoGovernanceBadges from "../lib/components/IsoGovernanceBadges.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";

  interface Props {
    initialProjectId?: number | null;
    onSelectProjectForViewer?:
      ((projectId: number, elementGuid?: string, bcfArtifactId?: number) => void) | undefined;
  }

  let { initialProjectId = null, onSelectProjectForViewer = undefined }: Props = $props();

  let projects: Project[] = $state([]);
  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  let result: AnalysisResult | null = null;
  let isLoading = false;
  let error = $state("");

  // ARCH BCF Artifacts
  let bcfArtifacts: BcfArtifact[] = $state([]);
  let isBcfLoading = $state(false);
  let filterToSelectedProject = $state(false);
  let selectedArtifactIds: number[] = $state([]);
  let isDeleteArtifactModalOpen = $state(false);
  let artifactToDelete: BcfArtifact | null = $state(null);
  let isBulkDeleteArtifactsModalOpen = $state(false);

  // Artifact search, filter & sort
  let artifactSearchQuery = $state("");
  let artifactSortField: "id" | "filename" | "issue_count" | "byte_size" | "created_at" =
    $state("id");
  let artifactSortAsc = $state(false);
  let artifactCurrentPage = $state(1);
  let artifactPageSize = $state(10);

  // Live BCF REST Topics
  let bcfTopics: BCFTopicResponse[] = $state([]);
  let isTopicsLoading = $state(false);
  let activeTab: "live_bcf" | "artifacts" = $state("live_bcf");
  let selectedTopicGuids: string[] = $state([]);

  // Topic search, filter & sort
  let topicSearchQuery = $state("");
  let topicStatusFilter = $state("ALL");
  let topicPriorityFilter = $state("ALL");
  let topicCdeFilter = $state("ALL");
  let topicSortField:
    "title" | "guid" | "topic_status" | "priority" | "cde_state" | "creation_date" =
    $state("creation_date");
  let topicSortAsc = $state(false);
  let topicCurrentPage = $state(1);
  let topicPageSize = $state(10);

  // Topic Modals State
  let isTopicCreateModalOpen = $state(false);
  let isTopicEditModalOpen = $state(false);
  let topicToEdit: BCFTopicResponse | null = $state(null);
  let isTopicDetailsModalOpen = $state(false);
  let topicToView: BCFTopicResponse | null = $state(null);
  let isTopicDeleteModalOpen = $state(false);
  let topicToDelete: BCFTopicResponse | null = $state(null);
  let isTopicBulkEditModalOpen = $state(false);
  let isTopicBulkDeleteModalOpen = $state(false);

  onMount(async () => {
    try {
      const [data] = await Promise.all([projectsApi.list(), loadBcfArtifacts()]);
      projects = data.projects || [];
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
      if (selectedProjectId) {
        await Promise.all([loadReport(), loadBcfTopics()]);
      }
    } catch {
      // ignore
    }
  });

  async function loadReport() {
    if (!selectedProjectId) return;
    isLoading = true;
    try {
      result = await analyzeApi.getResults(selectedProjectId, "corrosion");
    } catch {
      result = null;
    } finally {
      isLoading = false;
    }
  }

  async function loadBcfArtifacts() {
    isBcfLoading = true;
    try {
      bcfArtifacts = await analyzeApi.listBcfArtifacts();
    } catch {
      bcfArtifacts = [];
    } finally {
      isBcfLoading = false;
    }
  }

  async function loadBcfTopics() {
    if (!selectedProjectId) {
      bcfTopics = [];
      return;
    }
    isTopicsLoading = true;
    try {
      bcfTopics = await bcfApi.listTopics(selectedProjectId);
    } catch {
      bcfTopics = [];
    } finally {
      isTopicsLoading = false;
    }
  }

  function toggleSelectAllTopics() {
    if (allFilteredTopicsSelected) {
      selectedTopicGuids = [];
    } else {
      selectedTopicGuids = filteredTopics.map((t) => t.guid);
    }
  }

  function toggleSelectTopic(guid: string) {
    if (selectedTopicGuids.includes(guid)) {
      selectedTopicGuids = selectedTopicGuids.filter((g) => g !== guid);
    } else {
      selectedTopicGuids = [...selectedTopicGuids, guid];
    }
  }

  function toggleTopicSort(
    field: "title" | "guid" | "topic_status" | "priority" | "cde_state" | "creation_date",
  ) {
    if (topicSortField === field) {
      topicSortAsc = !topicSortAsc;
    } else {
      topicSortField = field;
      topicSortAsc = true;
    }
  }

  function exportTopicsToCsv() {
    const topicsToExport = bcfTopics.filter((t) => selectedTopicGuids.includes(t.guid));
    const target = topicsToExport.length ? topicsToExport : filteredTopics;
    const headers = [
      "GUID",
      "Title",
      "Type",
      "Status",
      "Priority",
      "CDEState",
      "Suitability",
      "Revision",
      "Assignee",
      "Created",
    ];
    const rows = target.map((t) => [
      t.guid,
      `"${(t.title || "").replace(/"/g, '""')}"`,
      `"${(t.topic_type || "Issue").replace(/"/g, '""')}"`,
      t.topic_status,
      t.priority,
      t.cde_state || "WIP",
      t.suitability_code || "S0",
      t.revision_code || "P01.01",
      `"${(t.assigned_to || "").replace(/"/g, '""')}"`,
      `"${t.creation_date || ""}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `bcf_topics_${currentProject?.name || "project"}_${new Date().toISOString().substring(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function openTopicDetails(topic: BCFTopicResponse) {
    topicToView = topic;
    isTopicDetailsModalOpen = true;
  }

  function openTopicEdit(topic: BCFTopicResponse) {
    topicToEdit = topic;
    isTopicEditModalOpen = true;
  }

  function promptDeleteTopic(topic: BCFTopicResponse) {
    topicToDelete = topic;
    isTopicDeleteModalOpen = true;
  }

  async function confirmDeleteTopic() {
    if (!topicToDelete || !selectedProjectId) return;
    try {
      await bcfApi.deleteTopic(selectedProjectId, topicToDelete.guid);
      bcfTopics = bcfTopics.filter((t) => t.guid !== topicToDelete!.guid);
      selectedTopicGuids = selectedTopicGuids.filter((g) => g !== topicToDelete!.guid);
      topicToDelete = null;
    } catch (err: any) {
      error = `Failed to delete topic: ${err.message}`;
    }
  }

  async function confirmBulkDeleteTopics() {
    if (!selectedTopicGuids.length || !selectedProjectId) return;
    try {
      await bcfApi.bulkDeleteTopics(selectedProjectId, selectedTopicGuids);
      bcfTopics = bcfTopics.filter((t) => !selectedTopicGuids.includes(t.guid));
      selectedTopicGuids = [];
      isTopicBulkDeleteModalOpen = false;
    } catch (err: any) {
      error = `Failed to delete selected topics: ${err.message}`;
    }
  }

  function toggleSelectAllArtifacts() {
    if (allFilteredArtifactsSelected) {
      selectedArtifactIds = [];
    } else {
      selectedArtifactIds = displayedBcfArtifacts.map((a) => a.id);
    }
  }

  function toggleSelectArtifact(id: number) {
    if (selectedArtifactIds.includes(id)) {
      selectedArtifactIds = selectedArtifactIds.filter((aId) => aId !== id);
    } else {
      selectedArtifactIds = [...selectedArtifactIds, id];
    }
  }

  function toggleArtifactSort(
    field: "id" | "filename" | "issue_count" | "byte_size" | "created_at",
  ) {
    if (artifactSortField === field) {
      artifactSortAsc = !artifactSortAsc;
    } else {
      artifactSortField = field;
      artifactSortAsc = true;
    }
  }

  function exportArtifactsToCsv() {
    const target = selectedArtifactIds.length
      ? bcfArtifacts.filter((a) => selectedArtifactIds.includes(a.id))
      : displayedBcfArtifacts;
    const headers = [
      "ID",
      "ProjectID",
      "ProjectName",
      "Filename",
      "Issues",
      "ByteSize",
      "CreatedAt",
    ];
    const rows = target.map((a) => [
      a.id,
      a.project_id,
      `"${getProjectName(a.project_id).replace(/"/g, '""')}"`,
      `"${(a.filename || "").replace(/"/g, '""')}"`,
      a.issue_count,
      a.byte_size,
      `"${a.created_at || ""}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `bcf_artifacts_export_${new Date().toISOString().substring(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function promptDeleteArtifact(artifact: BcfArtifact) {
    artifactToDelete = artifact;
    isDeleteArtifactModalOpen = true;
  }

  async function confirmDeleteArtifact() {
    if (!artifactToDelete) return;
    try {
      await analyzeApi.deleteBcfArtifact(artifactToDelete.id);
      bcfArtifacts = bcfArtifacts.filter((a) => a.id !== artifactToDelete!.id);
      selectedArtifactIds = selectedArtifactIds.filter((id) => id !== artifactToDelete!.id);
      artifactToDelete = null;
    } catch (err: any) {
      error = `Failed to delete BCF artifact: ${err.message}`;
    }
  }

  async function confirmBulkDeleteArtifacts() {
    if (!selectedArtifactIds.length) return;
    try {
      for (const id of selectedArtifactIds) {
        await analyzeApi.deleteBcfArtifact(id);
      }
      bcfArtifacts = bcfArtifacts.filter((a) => !selectedArtifactIds.includes(a.id));
      selectedArtifactIds = [];
      isBulkDeleteArtifactsModalOpen = false;
    } catch (err: any) {
      error = `Failed to delete selected BCF artifacts: ${err.message}`;
    }
  }

  function getProjectName(projId: number): string {
    const p = projects.find((x) => x.id === projId);
    return p ? p.name : `Project #${projId}`;
  }

  function formatBytes(bytes?: number): string {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  }

  function formatDate(dateStr?: string): string {
    if (!dateStr) return "—";
    try {
      return new Date(dateStr).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return dateStr;
    }
  }
  let currentProject = $derived(projects.find((p) => p.id === selectedProjectId));
  // --- TOPIC COMPUTATIONS & SELECTION ---
  let filteredTopics = $derived(
    (bcfTopics || [])
      .filter((t) => {
        const matchesSearch =
          !topicSearchQuery ||
          (t.title || "").toLowerCase().includes(topicSearchQuery.toLowerCase()) ||
          (t.guid || "").toLowerCase().includes(topicSearchQuery.toLowerCase()) ||
          (t.description || "").toLowerCase().includes(topicSearchQuery.toLowerCase()) ||
          (t.assigned_to || "").toLowerCase().includes(topicSearchQuery.toLowerCase());
        const matchesStatus =
          topicStatusFilter === "ALL" || (t.topic_status || "Open") === topicStatusFilter;
        const matchesPriority =
          topicPriorityFilter === "ALL" || (t.priority || "Normal") === topicPriorityFilter;
        const matchesCde = topicCdeFilter === "ALL" || (t.cde_state || "WIP") === topicCdeFilter;
        return matchesSearch && matchesStatus && matchesPriority && matchesCde;
      })
      .sort((a, b) => {
        let valA: any = a[topicSortField];
        let valB: any = b[topicSortField];
        if (valA === undefined || valA === null) valA = "";
        if (valB === undefined || valB === null) valB = "";
        if (typeof valA === "string") valA = valA.toLowerCase();
        if (typeof valB === "string") valB = valB.toLowerCase();
        if (valA < valB) return topicSortAsc ? -1 : 1;
        if (valA > valB) return topicSortAsc ? 1 : -1;
        return 0;
      }),
  );
  let topicTotalItems = $derived(filteredTopics.length);
  let paginatedTopics = $derived(
    filteredTopics.slice((topicCurrentPage - 1) * topicPageSize, topicCurrentPage * topicPageSize),
  );
  let allFilteredTopicsSelected = $derived(
    filteredTopics.length > 0 && filteredTopics.every((t) => selectedTopicGuids.includes(t.guid)),
  );
  // --- ARTIFACTS COMPUTATIONS & SELECTION ---
  let displayedBcfArtifacts = $derived(
    (filterToSelectedProject && selectedProjectId
      ? bcfArtifacts.filter((a) => a.project_id === selectedProjectId)
      : bcfArtifacts
    )
      .filter((a) => {
        const projName = getProjectName(a.project_id);
        return (
          !artifactSearchQuery ||
          (a.filename || "").toLowerCase().includes(artifactSearchQuery.toLowerCase()) ||
          projName.toLowerCase().includes(artifactSearchQuery.toLowerCase())
        );
      })
      .sort((a, b) => {
        let valA: any = a[artifactSortField];
        let valB: any = b[artifactSortField];
        if (valA === undefined || valA === null) valA = "";
        if (valB === undefined || valB === null) valB = "";
        if (typeof valA === "string") valA = valA.toLowerCase();
        if (typeof valB === "string") valB = valB.toLowerCase();
        if (valA < valB) return artifactSortAsc ? -1 : 1;
        if (valA > valB) return artifactSortAsc ? 1 : -1;
        return 0;
      }),
  );
  let artifactTotalItems = $derived(displayedBcfArtifacts.length);
  let paginatedArtifacts = $derived(
    displayedBcfArtifacts.slice(
      (artifactCurrentPage - 1) * artifactPageSize,
      artifactCurrentPage * artifactPageSize,
    ),
  );
  let allFilteredArtifactsSelected = $derived(
    displayedBcfArtifacts.length > 0 &&
      displayedBcfArtifacts.every((a) => selectedArtifactIds.includes(a.id)),
  );
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="Reports"
    title="Compliance Reports & Exports"
    subtitle="Generate, track, and download OpenBIM compliance audit deliverables in BCF 2.1, CSV, and JSON."
    icon={FolderArchive}
  >
    {#snippet actions()}
      <div class="flex items-center gap-2">
        <select
          bind:value={selectedProjectId}
          onchange={() => {
            loadReport();
            loadBcfTopics();
          }}
          class="rounded-xl border border-slate-800 bg-slate-900 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          {#each projects as p}
            <option value={p.id}>{p.name}</option>
          {/each}
        </select>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
      {error}
    </div>
  {/if}

  {#if selectedProjectId}
    <!-- ═══ BCF Deliverables & Live Topics Hub ═══ -->
    <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
      <div class="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <div class="flex items-center gap-2">
            <FolderArchive class="h-4 w-4 text-blue-400" />
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              buildingSMART BCF Collaboration Hub
            </h2>
            <span
              class="rounded-full border border-slate-700 bg-slate-800 px-2 py-0.5 text-micro font-semibold text-slate-300"
            >
              {activeTab === "live_bcf"
                ? `${bcfTopics.length} Live Topics`
                : `${bcfArtifacts.length} Artifacts`}
            </span>
          </div>
          <p class="mt-1 text-xs text-slate-400">
            Bidirectional BCF REST API v2.1/v3.0 live topics exchange and persisted BCF zip
            deliverables with ISO 19650 governance tags.
          </p>
        </div>

        <!-- Tab & Action Controls -->
        <div class="flex shrink-0 flex-wrap items-center gap-2.5">
          <div
            class="flex items-center rounded-xl border border-slate-800 bg-slate-950 p-1 text-xs"
          >
            <button
              type="button"
              onclick={() => (activeTab = "live_bcf")}
              class="rounded-lg px-3 py-1 font-medium transition-colors {activeTab === 'live_bcf'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-50'}"
            >
              Live BCF 2.1 Topics
            </button>
            <button
              type="button"
              onclick={() => (activeTab = "artifacts")}
              class="rounded-lg px-3 py-1 font-medium transition-colors {activeTab === 'artifacts'
                ? 'bg-slate-800 text-slate-50'
                : 'text-slate-400 hover:text-slate-50'}"
            >
              BCF Zip Artifacts
            </button>
          </div>

          {#if activeTab === "live_bcf"}
            <button
              type="button"
              onclick={() => (isTopicCreateModalOpen = true)}
              class="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-blue-500"
            >
              <Plus class="h-3.5 w-3.5" />
              <span>Create Topic</span>
            </button>
          {/if}

          <button
            type="button"
            onclick={() => {
              if (activeTab === "live_bcf") loadBcfTopics();
              else loadBcfArtifacts();
            }}
            disabled={isTopicsLoading || isBcfLoading}
            class="rounded-xl border border-slate-700 bg-slate-800 p-2 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50 disabled:opacity-50"
            title="Refresh Deliverables"
          >
            <RefreshCw
              class="h-3.5 w-3.5 {isTopicsLoading || isBcfLoading ? 'animate-spin' : ''}"
            />
          </button>
        </div>
      </div>

      {#if activeTab === "live_bcf"}
        <!-- ── TAB 1: LIVE BCF 2.1 TOPICS ── -->

        <!-- Filters & Search Toolbar -->
        <div
          class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800/90 bg-slate-950/80 p-3.5 md:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              bind:value={topicSearchQuery}
              placeholder="Search topics by title, GUID, assignee, or description..."
              class="w-full rounded-xl border border-slate-800 bg-slate-900 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>

          <div class="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <select
              bind:value={topicStatusFilter}
              class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="ALL">All Statuses</option>
              <option value="Open">Open</option>
              <option value="In Progress">In Progress</option>
              <option value="Resolved">Resolved</option>
              <option value="Closed">Closed</option>
            </select>

            <select
              bind:value={topicPriorityFilter}
              class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="ALL">All Priorities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Normal">Normal</option>
              <option value="Low">Low</option>
            </select>

            <select
              bind:value={topicCdeFilter}
              class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="ALL">All CDE States</option>
              <option value="WIP">WIP</option>
              <option value="SHARED">SHARED</option>
              <option value="PUBLISHED">PUBLISHED</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          </div>
        </div>

        <!-- Bulk Action Toolbar -->
        <BulkActionBar
          selectedCount={selectedTopicGuids.length}
          itemLabel="BCF topic"
          onClearSelection={() => (selectedTopicGuids = [])}
          onBulkEdit={() => (isTopicBulkEditModalOpen = true)}
          onBulkExport={exportTopicsToCsv}
          onBulkDelete={() => (isTopicBulkDeleteModalOpen = true)}
        />

        {#if isTopicsLoading && bcfTopics.length === 0}
          <LoadingState
            message={`Querying /api/bcf/v2.1/projects/${selectedProjectId}/topics...`}
          />
        {:else if filteredTopics.length === 0}
          <div class="p-6">
            <EmptyState
              title={`No BCF topics match your criteria for ${currentProject?.name || "this project"}`}
              description="Create a topic or adjust filters to coordinate model findings."
              actionLabel={topicSearchQuery ||
              topicStatusFilter !== "ALL" ||
              topicPriorityFilter !== "ALL"
                ? "Reset Filters"
                : "+ Create BCF Topic"}
              onAction={() => {
                if (
                  topicSearchQuery ||
                  topicStatusFilter !== "ALL" ||
                  topicPriorityFilter !== "ALL"
                ) {
                  topicSearchQuery = "";
                  topicStatusFilter = "ALL";
                  topicPriorityFilter = "ALL";
                  topicCdeFilter = "ALL";
                } else {
                  isTopicCreateModalOpen = true;
                }
              }}
            />
          </div>
        {:else}
          <div class="overflow-x-auto rounded-xl border border-slate-800/80">
            <table class="w-full border-collapse text-left text-xs">
              <thead>
                <tr
                  class="border-b border-slate-800 bg-slate-950/60 text-micro font-semibold uppercase tracking-wider text-slate-400"
                >
                  <th class="w-10 px-4 py-3">
                    <TableCheckbox
                      checked={allFilteredTopicsSelected}
                      onchange={toggleSelectAllTopics}
                      title="Select all topics"
                    />
                  </th>
                  <SortHeader
                    column="guid"
                    sortField={topicSortField}
                    sortAsc={topicSortAsc}
                    onSort={toggleTopicSort}
                  >
                    Topic GUID
                  </SortHeader>
                  <SortHeader
                    column="title"
                    sortField={topicSortField}
                    sortAsc={topicSortAsc}
                    onSort={toggleTopicSort}
                  >
                    Title & Type
                  </SortHeader>
                  <SortHeader
                    column="topic_status"
                    sortField={topicSortField}
                    sortAsc={topicSortAsc}
                    onSort={toggleTopicSort}
                  >
                    Status & Priority
                  </SortHeader>
                  <SortHeader
                    column="cde_state"
                    sortField={topicSortField}
                    sortAsc={topicSortAsc}
                    onSort={toggleTopicSort}
                  >
                    ISO 19650 Governance
                  </SortHeader>
                  <th class="px-4 py-3">Elements</th>
                  <th class="px-4 py-3">Viewpoints</th>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each paginatedTopics as topic}
                  <tr
                    class="transition-colors hover:bg-slate-900/60 {selectedTopicGuids.includes(
                      topic.guid,
                    )
                      ? 'bg-blue-950/20'
                      : ''}"
                  >
                    <td class="w-10 px-4 py-3">
                      <TableCheckbox
                        checked={selectedTopicGuids.includes(topic.guid)}
                        onchange={() => toggleSelectTopic(topic.guid)}
                        ariaLabel={`Select topic ${topic.title}`}
                      />
                    </td>
                    <td class="px-4 py-3 font-mono text-caption text-slate-400">
                      {topic.guid.substring(0, 8)}...
                    </td>
                    <td class="px-4 py-3">
                      <div class="font-medium text-slate-50">{topic.title}</div>
                      <div class="text-micro text-slate-400">
                        {topic.topic_type || "Clash / Compliance"}
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-1.5">
                        <SeverityBadge severity={topic.topic_status || "Open"} />
                        <span class="text-micro font-medium text-slate-400">
                          {topic.priority || "Normal"}
                        </span>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <IsoGovernanceBadges
                        suitability={topic.suitability_code || "S0"}
                        revision={topic.revision_code || "P01.01"}
                        cdeState={topic.cde_state || "WIP"}
                      />
                    </td>
                    <td class="px-4 py-3 font-mono text-slate-300">
                      {topic.component_guids ? topic.component_guids.length : 0} GUID{topic
                        .component_guids?.length === 1
                        ? ""
                        : "s"}
                    </td>
                    <td class="px-4 py-3">
                      <span class="inline-flex items-center gap-1 text-caption text-slate-300">
                        <Camera class="h-3 w-3 text-blue-400" />
                        <span>{topic.viewpoints_count || 1}</span>
                      </span>
                    </td>
                    <td class="whitespace-nowrap px-4 py-3 text-right">
                      <div class="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onclick={() => openTopicDetails(topic)}
                          class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                          title="View topic discussion & viewpoints"
                        >
                          <Eye class="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onclick={() => openTopicEdit(topic)}
                          class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-blue-950/30 hover:text-blue-400"
                          title="Edit topic"
                        >
                          <Pencil class="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onclick={() => promptDeleteTopic(topic)}
                          class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                          title="Delete topic"
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
            currentPage={topicCurrentPage}
            pageSize={topicPageSize}
            totalItems={topicTotalItems}
            onPageChange={(p) => (topicCurrentPage = p)}
            onPageSizeChange={(s) => {
              topicPageSize = s;
              topicCurrentPage = 1;
            }}
          />
        {/if}
      {:else}
        <!-- ── TAB 2: ARCHIVED BCF ZIP ARTIFACTS ── -->

        <!-- Filters & Project Filter Toolbar -->
        <div
          class="flex flex-col items-center justify-between gap-3 rounded-2xl border border-slate-800/90 bg-slate-950/80 p-3.5 sm:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              bind:value={artifactSearchQuery}
              placeholder="Filter BCF archives by filename or project..."
              class="w-full rounded-xl border border-slate-800 bg-slate-900 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>

          {#if selectedProjectId}
            <div
              class="flex items-center rounded-xl border border-slate-800 bg-slate-900 p-1 text-xs"
            >
              <button
                type="button"
                onclick={() => (filterToSelectedProject = false)}
                class="rounded-lg px-2.5 py-1 font-medium transition-colors {!filterToSelectedProject
                  ? 'bg-slate-800 text-slate-50'
                  : 'text-slate-400 hover:text-slate-50'}"
              >
                All Projects
              </button>
              <button
                type="button"
                onclick={() => (filterToSelectedProject = true)}
                class="rounded-lg px-2.5 py-1 font-medium transition-colors {filterToSelectedProject
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-slate-50'}"
              >
                {currentProject?.name || "Selected"}
              </button>
            </div>
          {/if}
        </div>

        <!-- Bulk Action Bar for Artifacts -->
        <BulkActionBar
          selectedCount={selectedArtifactIds.length}
          itemLabel="BCF artifact"
          onClearSelection={() => (selectedArtifactIds = [])}
          onBulkExport={exportArtifactsToCsv}
          onBulkDelete={() => (isBulkDeleteArtifactsModalOpen = true)}
        />

        {#if isBcfLoading && bcfArtifacts.length === 0}
          <div class="p-12 text-center text-xs text-slate-400">
            <div
              class="mx-auto mb-2 h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent"
            ></div>
            Loading BCF artifacts…
          </div>
        {:else if displayedBcfArtifacts.length === 0}
          <div
            class="rounded-xl border border-dashed border-slate-800 p-12 text-center text-xs text-slate-500"
          >
            {filterToSelectedProject
              ? `No BCF reports found for ${currentProject?.name || "this project"}. Run an ARCH Compliance Audit to generate one.`
              : "No persisted BCF artifacts found matching your filter."}
          </div>
        {:else}
          <div class="overflow-x-auto rounded-xl border border-slate-800/80">
            <table class="w-full border-collapse text-left text-xs">
              <thead>
                <tr
                  class="border-b border-slate-800 bg-slate-950/60 text-micro font-semibold uppercase tracking-wider text-slate-400"
                >
                  <th class="w-10 px-4 py-3">
                    <TableCheckbox
                      checked={allFilteredArtifactsSelected}
                      onchange={toggleSelectAllArtifacts}
                      title="Select all BCF artifacts"
                    />
                  </th>
                  <SortHeader
                    column="id"
                    sortField={artifactSortField}
                    sortAsc={artifactSortAsc}
                    onSort={toggleArtifactSort}
                  >
                    ID
                  </SortHeader>
                  <th class="px-4 py-3">Project</th>
                  <SortHeader
                    column="filename"
                    sortField={artifactSortField}
                    sortAsc={artifactSortAsc}
                    onSort={toggleArtifactSort}
                  >
                    Artifact / Filename
                  </SortHeader>
                  <SortHeader
                    column="issue_count"
                    sortField={artifactSortField}
                    sortAsc={artifactSortAsc}
                    onSort={toggleArtifactSort}
                  >
                    Issues
                  </SortHeader>
                  <SortHeader
                    column="byte_size"
                    sortField={artifactSortField}
                    sortAsc={artifactSortAsc}
                    onSort={toggleArtifactSort}
                  >
                    Size
                  </SortHeader>
                  <SortHeader
                    column="created_at"
                    sortField={artifactSortField}
                    sortAsc={artifactSortAsc}
                    onSort={toggleArtifactSort}
                  >
                    Date
                  </SortHeader>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each paginatedArtifacts as artifact}
                  <tr
                    class="transition-colors hover:bg-slate-900/60 {selectedArtifactIds.includes(
                      artifact.id,
                    )
                      ? 'bg-blue-950/20'
                      : ''}"
                  >
                    <td class="w-10 px-4 py-3">
                      <TableCheckbox
                        checked={selectedArtifactIds.includes(artifact.id)}
                        onchange={() => toggleSelectArtifact(artifact.id)}
                        ariaLabel={`Select artifact ${artifact.filename}`}
                      />
                    </td>
                    <td class="px-4 py-3 font-mono text-slate-500">#{artifact.id}</td>
                    <td class="px-4 py-3 font-medium text-slate-50">
                      {getProjectName(artifact.project_id)}
                    </td>
                    <td class="px-4 py-3">
                      <div
                        class="max-w-xs truncate font-mono text-slate-300"
                        title={artifact.filename}
                      >
                        {artifact.filename}
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-block rounded-full border px-2.5 py-0.5 text-micro font-semibold {artifact.issue_count >
                        0
                          ? 'border-rose-800 bg-rose-950/60 text-rose-300'
                          : 'border-emerald-800 bg-emerald-950/60 text-emerald-300'}"
                      >
                        {artifact.issue_count} issue{artifact.issue_count === 1 ? "" : "s"}
                      </span>
                    </td>
                    <td class="px-4 py-3 font-mono text-slate-400">
                      {formatBytes(artifact.byte_size)}
                    </td>
                    <td class="whitespace-nowrap px-4 py-3 text-slate-400">
                      {formatDate(artifact.created_at)}
                    </td>
                    <td class="px-4 py-3 text-right">
                      <div class="inline-flex items-center justify-end gap-1.5">
                        {#if onSelectProjectForViewer}
                          <button
                            type="button"
                            onclick={() =>
                              onSelectProjectForViewer &&
                              onSelectProjectForViewer(artifact.project_id, undefined, artifact.id)}
                            class="inline-flex items-center gap-1 rounded-lg border border-emerald-800 bg-emerald-900/40 px-2.5 py-1 text-xs font-semibold text-emerald-300 transition-colors hover:bg-emerald-800/60"
                            title="Open 3D Viewer with this BCF Report"
                          >
                            <ScanEye class="h-3.5 w-3.5" />
                            View 3D
                          </button>
                        {/if}
                        <a
                          href={analyzeApi.getBcfArtifactUrl(artifact.id)}
                          download
                          class="inline-flex items-center gap-1 rounded-lg border border-blue-500/30 bg-blue-600/20 px-2.5 py-1 text-xs font-semibold text-blue-300 transition-colors hover:bg-blue-600/30"
                          title="Download BCF 2.1 Zip"
                        >
                          <Download class="h-3.5 w-3.5" />
                          Zip
                        </a>
                        <button
                          type="button"
                          onclick={() => promptDeleteArtifact(artifact)}
                          class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                          title="Delete BCF archive"
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
            currentPage={artifactCurrentPage}
            pageSize={artifactPageSize}
            totalItems={artifactTotalItems}
            onPageChange={(p) => (artifactCurrentPage = p)}
            onPageSizeChange={(s) => {
              artifactPageSize = s;
              artifactCurrentPage = 1;
            }}
          />
        {/if}
      {/if}
    </div>
  {:else}
    <div
      class="rounded-2xl border border-dashed border-slate-800 p-16 text-center text-xs text-slate-500"
    >
      Select a project to generate and export compliance audit deliverables.
    </div>
  {/if}
</div>

<!-- ═══ MODALS ═══ -->
{#if selectedProjectId}
  <!-- Create BCF Topic Modal -->
  <BcfTopicEditModal
    isOpen={isTopicCreateModalOpen}
    projectId={selectedProjectId}
    topicToEdit={null}
    onClose={() => (isTopicCreateModalOpen = false)}
    onSaved={(newTopic) => {
      bcfTopics = [newTopic, ...bcfTopics];
    }}
  />

  <!-- Edit BCF Topic Modal -->
  <BcfTopicEditModal
    isOpen={isTopicEditModalOpen}
    projectId={selectedProjectId}
    {topicToEdit}
    onClose={() => {
      isTopicEditModalOpen = false;
      topicToEdit = null;
    }}
    onSaved={(updated) => {
      bcfTopics = bcfTopics.map((t) => (t.guid === updated.guid ? updated : t));
    }}
  />

  <!-- BCF Topic Details Modal -->
  <BcfTopicDetailsModal
    isOpen={isTopicDetailsModalOpen}
    projectId={selectedProjectId}
    topic={topicToView}
    onClose={() => {
      isTopicDetailsModalOpen = false;
      topicToView = null;
    }}
    onSelectViewer={(pId, guid) => {
      isTopicDetailsModalOpen = false;
      if (onSelectProjectForViewer) onSelectProjectForViewer(pId, guid);
    }}
  />

  <!-- Bulk Edit BCF Topics Modal -->
  <BcfBulkEditModal
    isOpen={isTopicBulkEditModalOpen}
    projectId={selectedProjectId}
    {selectedTopicGuids}
    onClose={() => (isTopicBulkEditModalOpen = false)}
    onBulkUpdated={() => {
      loadBcfTopics();
      selectedTopicGuids = [];
    }}
  />

  <!-- Delete Single BCF Topic Modal -->
  <ConfirmModal
    bind:isOpen={isTopicDeleteModalOpen}
    title="Delete BCF Topic"
    message={`Are you sure you want to delete topic "${topicToDelete?.title || ""}"? This will also remove all associated viewpoints and discussion history.`}
    confirmText="Delete Topic"
    danger={true}
    onConfirm={confirmDeleteTopic}
    onCancel={() => (topicToDelete = null)}
  />

  <!-- Bulk Delete BCF Topics Modal -->
  <ConfirmModal
    bind:isOpen={isTopicBulkDeleteModalOpen}
    title="Delete Selected Topics"
    message={`Are you sure you want to delete ${selectedTopicGuids.length} selected BCF topic(s)? This cannot be undone.`}
    confirmText="Delete Selected Topics"
    danger={true}
    onConfirm={confirmBulkDeleteTopics}
    onCancel={() => (selectedTopicGuids = [])}
  />
{/if}

<!-- Delete Single BCF Artifact Modal -->
<ConfirmModal
  bind:isOpen={isDeleteArtifactModalOpen}
  title="Delete BCF Report Artifact"
  message={`Are you sure you want to delete BCF report archive "${artifactToDelete?.filename || ""}"?`}
  confirmText="Delete BCF Archive"
  danger={true}
  onConfirm={confirmDeleteArtifact}
  onCancel={() => (artifactToDelete = null)}
/>

<!-- Bulk Delete BCF Artifacts Modal -->
<ConfirmModal
  bind:isOpen={isBulkDeleteArtifactsModalOpen}
  title="Delete Selected BCF Archives"
  message={`Are you sure you want to delete ${selectedArtifactIds.length} selected BCF report archive(s)?`}
  confirmText="Delete Selected Archives"
  danger={true}
  onConfirm={confirmBulkDeleteArtifacts}
  onCancel={() => (selectedArtifactIds = [])}
/>
