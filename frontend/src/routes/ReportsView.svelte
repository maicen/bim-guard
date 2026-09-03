<script lang="ts">
  import { onMount } from "svelte";
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

  export let initialProjectId: number | null = null;
  export let onSelectProjectForViewer:
    | ((projectId: number, elementGuid?: string, bcfArtifactId?: number) => void)
    | undefined = undefined;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let result: AnalysisResult | null = null;
  let isLoading = false;
  let error = "";

  // ARCH BCF Artifacts
  let bcfArtifacts: BcfArtifact[] = [];
  let isBcfLoading = false;
  let filterToSelectedProject = false;
  let selectedArtifactIds: number[] = [];
  let isDeleteArtifactModalOpen = false;
  let artifactToDelete: BcfArtifact | null = null;
  let isBulkDeleteArtifactsModalOpen = false;

  // Artifact search, filter & sort
  let artifactSearchQuery = "";
  let artifactSortField: "id" | "filename" | "issue_count" | "byte_size" | "created_at" = "id";
  let artifactSortAsc = false;
  let artifactCurrentPage = 1;
  let artifactPageSize = 10;

  // Live BCF REST Topics
  let bcfTopics: BCFTopicResponse[] = [];
  let isTopicsLoading = false;
  let activeTab: "live_bcf" | "artifacts" = "live_bcf";
  let selectedTopicGuids: string[] = [];

  // Topic search, filter & sort
  let topicSearchQuery = "";
  let topicStatusFilter = "ALL";
  let topicPriorityFilter = "ALL";
  let topicCdeFilter = "ALL";
  let topicSortField: "title" | "guid" | "topic_status" | "priority" | "cde_state" | "creation_date" = "creation_date";
  let topicSortAsc = false;
  let topicCurrentPage = 1;
  let topicPageSize = 10;

  // Topic Modals State
  let isTopicCreateModalOpen = false;
  let isTopicEditModalOpen = false;
  let topicToEdit: BCFTopicResponse | null = null;
  let isTopicDetailsModalOpen = false;
  let topicToView: BCFTopicResponse | null = null;
  let isTopicDeleteModalOpen = false;
  let topicToDelete: BCFTopicResponse | null = null;
  let isTopicBulkEditModalOpen = false;
  let isTopicBulkDeleteModalOpen = false;

  onMount(async () => {
    try {
      const [data] = await Promise.all([
        projectsApi.list(),
        loadBcfArtifacts(),
      ]);
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

  $: currentProject = projects.find((p) => p.id === selectedProjectId);

  // --- TOPIC COMPUTATIONS & SELECTION ---
  $: filteredTopics = (bcfTopics || [])
    .filter((t) => {
      const matchesSearch =
        !topicSearchQuery ||
        (t.title || "").toLowerCase().includes(topicSearchQuery.toLowerCase()) ||
        (t.guid || "").toLowerCase().includes(topicSearchQuery.toLowerCase()) ||
        (t.description || "").toLowerCase().includes(topicSearchQuery.toLowerCase()) ||
        (t.assigned_to || "").toLowerCase().includes(topicSearchQuery.toLowerCase());
      const matchesStatus = topicStatusFilter === "ALL" || (t.topic_status || "Open") === topicStatusFilter;
      const matchesPriority = topicPriorityFilter === "ALL" || (t.priority || "Normal") === topicPriorityFilter;
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
    });

  $: topicTotalItems = filteredTopics.length;
  $: paginatedTopics = filteredTopics.slice(
    (topicCurrentPage - 1) * topicPageSize,
    topicCurrentPage * topicPageSize,
  );

  $: allFilteredTopicsSelected =
    filteredTopics.length > 0 &&
    filteredTopics.every((t) => selectedTopicGuids.includes(t.guid));

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

  function toggleTopicSort(field: "title" | "guid" | "topic_status" | "priority" | "cde_state" | "creation_date") {
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
    const headers = ["GUID", "Title", "Type", "Status", "Priority", "CDEState", "Suitability", "Revision", "Assignee", "Created"];
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
    link.setAttribute("download", `bcf_topics_${currentProject?.name || "project"}_${new Date().toISOString().substring(0, 10)}.csv`);
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

  // --- ARTIFACTS COMPUTATIONS & SELECTION ---
  $: displayedBcfArtifacts = (filterToSelectedProject && selectedProjectId
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
    });

  $: artifactTotalItems = displayedBcfArtifacts.length;
  $: paginatedArtifacts = displayedBcfArtifacts.slice(
    (artifactCurrentPage - 1) * artifactPageSize,
    artifactCurrentPage * artifactPageSize,
  );

  $: allFilteredArtifactsSelected =
    displayedBcfArtifacts.length > 0 &&
    displayedBcfArtifacts.every((a) => selectedArtifactIds.includes(a.id));

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

  function toggleArtifactSort(field: "id" | "filename" | "issue_count" | "byte_size" | "created_at") {
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
    const headers = ["ID", "ProjectID", "ProjectName", "Filename", "Issues", "ByteSize", "CreatedAt"];
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
    link.setAttribute("download", `bcf_artifacts_export_${new Date().toISOString().substring(0, 10)}.csv`);
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
</script>

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <PageHeader
    category="Reports"
    title="Compliance Reports & Exports"
    subtitle="Generate, track, and download OpenBIM compliance audit deliverables in BCF 2.1, CSV, and JSON."
    icon={FolderArchive}
  >
    <div slot="actions" class="flex items-center gap-2">
      <select
        bind:value={selectedProjectId}
        on:change={() => {
          loadReport();
          loadBcfTopics();
        }}
        class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-slate-50 focus:outline-none focus:border-accent"
      >
        {#each projects as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </div>
  </PageHeader>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  {#if selectedProjectId}
    <!-- ═══ BCF Deliverables & Live Topics Hub ═══ -->
    <div
      class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4"
    >
      <div
        class="flex flex-col sm:flex-row sm:items-center justify-between gap-3"
      >
        <div>
          <div class="flex items-center gap-2">
            <FolderArchive class="w-4 h-4 text-blue-400" />
            <h2 class="text-base font-bold text-slate-50 tracking-tight">
              buildingSMART BCF Collaboration Hub
            </h2>
            <span
              class="px-2 py-0.5 rounded-full text-micro font-semibold bg-slate-800 text-slate-300 border border-slate-700"
            >
              {activeTab === 'live_bcf' ? `${bcfTopics.length} Live Topics` : `${bcfArtifacts.length} Artifacts`}
            </span>
          </div>
          <p class="text-xs text-slate-400 mt-1">
            Bidirectional BCF REST API v2.1/v3.0 live topics exchange and persisted BCF zip deliverables with ISO 19650 governance tags.
          </p>
        </div>

        <!-- Tab & Action Controls -->
        <div class="flex items-center gap-2.5 shrink-0 flex-wrap">
          <div
            class="flex items-center rounded-xl bg-slate-950 p-1 border border-slate-800 text-xs"
          >
            <button
              type="button"
              on:click={() => (activeTab = "live_bcf")}
              class="px-3 py-1 rounded-lg font-medium transition-colors {activeTab === 'live_bcf'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-50'}"
            >
              Live BCF 2.1 Topics
            </button>
            <button
              type="button"
              on:click={() => (activeTab = "artifacts")}
              class="px-3 py-1 rounded-lg font-medium transition-colors {activeTab === 'artifacts'
                ? 'bg-slate-800 text-slate-50'
                : 'text-slate-400 hover:text-slate-50'}"
            >
              BCF Zip Artifacts
            </button>
          </div>

          {#if activeTab === "live_bcf"}
            <button
              type="button"
              on:click={() => (isTopicCreateModalOpen = true)}
              class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-colors"
            >
              <Plus class="w-3.5 h-3.5" />
              <span>Create Topic</span>
            </button>
          {/if}

          <button
            type="button"
            on:click={() => {
              if (activeTab === 'live_bcf') loadBcfTopics();
              else loadBcfArtifacts();
            }}
            disabled={isTopicsLoading || isBcfLoading}
            class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-50 border border-slate-700 transition-colors disabled:opacity-50"
            title="Refresh Deliverables"
          >
            <RefreshCw
              class="w-3.5 h-3.5 {isTopicsLoading || isBcfLoading ? 'animate-spin' : ''}"
            />
          </button>
        </div>
      </div>

      {#if activeTab === "live_bcf"}
        <!-- ── TAB 1: LIVE BCF 2.1 TOPICS ── -->

        <!-- Filters & Search Toolbar -->
        <div class="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800/90 flex flex-col md:flex-row items-center gap-3">
          <div class="relative flex-1 w-full">
            <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              bind:value={topicSearchQuery}
              placeholder="Search topics by title, GUID, assignee, or description..."
              class="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-accent"
            />
          </div>

          <div class="flex items-center gap-2 w-full md:w-auto flex-wrap">
            <select
              bind:value={topicStatusFilter}
              class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 focus:outline-none focus:border-accent"
            >
              <option value="ALL">All Statuses</option>
              <option value="Open">Open</option>
              <option value="In Progress">In Progress</option>
              <option value="Resolved">Resolved</option>
              <option value="Closed">Closed</option>
            </select>

            <select
              bind:value={topicPriorityFilter}
              class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 focus:outline-none focus:border-accent"
            >
              <option value="ALL">All Priorities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Normal">Normal</option>
              <option value="Low">Low</option>
            </select>

            <select
              bind:value={topicCdeFilter}
              class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 focus:outline-none focus:border-accent"
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
          <LoadingState message={`Querying /api/bcf/v2.1/projects/${selectedProjectId}/topics...`} />
        {:else if filteredTopics.length === 0}
          <div class="p-6">
            <EmptyState
              title={`No BCF topics match your criteria for ${currentProject?.name || "this project"}`}
              description="Create a topic or adjust filters to coordinate model findings."
              actionLabel={topicSearchQuery || topicStatusFilter !== 'ALL' || topicPriorityFilter !== 'ALL' ? "Reset Filters" : "+ Create BCF Topic"}
              onAction={() => {
                if (topicSearchQuery || topicStatusFilter !== 'ALL' || topicPriorityFilter !== 'ALL') {
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
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr
                  class="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-semibold uppercase tracking-wider text-micro"
                >
                  <th class="py-3 px-4 w-10">
                    <TableCheckbox
                      checked={allFilteredTopicsSelected}
                      on:change={toggleSelectAllTopics}
                      title="Select all topics"
                    />
                  </th>
                  <SortHeader column="guid" sortField={topicSortField} sortAsc={topicSortAsc} onSort={toggleTopicSort}>
                    Topic GUID
                  </SortHeader>
                  <SortHeader column="title" sortField={topicSortField} sortAsc={topicSortAsc} onSort={toggleTopicSort}>
                    Title & Type
                  </SortHeader>
                  <SortHeader column="topic_status" sortField={topicSortField} sortAsc={topicSortAsc} onSort={toggleTopicSort}>
                    Status & Priority
                  </SortHeader>
                  <SortHeader column="cde_state" sortField={topicSortField} sortAsc={topicSortAsc} onSort={toggleTopicSort}>
                    ISO 19650 Governance
                  </SortHeader>
                  <th class="py-3 px-4">Elements</th>
                  <th class="py-3 px-4">Viewpoints</th>
                  <th class="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each paginatedTopics as topic}
                  <tr class="hover:bg-slate-900/60 transition-colors {selectedTopicGuids.includes(topic.guid) ? 'bg-blue-950/20' : ''}">
                    <td class="py-3 px-4 w-10">
                      <TableCheckbox
                        checked={selectedTopicGuids.includes(topic.guid)}
                        on:change={() => toggleSelectTopic(topic.guid)}
                        ariaLabel={`Select topic ${topic.title}`}
                      />
                    </td>
                    <td class="py-3 px-4 font-mono text-caption text-slate-400">
                      {topic.guid.substring(0, 8)}...
                    </td>
                    <td class="py-3 px-4">
                      <div class="font-medium text-slate-50">{topic.title}</div>
                      <div class="text-micro text-slate-400">{topic.topic_type || 'Clash / Compliance'}</div>
                    </td>
                    <td class="py-3 px-4">
                      <div class="flex items-center gap-1.5">
                        <SeverityBadge severity={topic.topic_status || 'Open'} />
                        <span class="text-micro text-slate-400 font-medium">
                          {topic.priority || 'Normal'}
                        </span>
                      </div>
                    </td>
                    <td class="py-3 px-4">
                      <IsoGovernanceBadges
                        suitability={topic.suitability_code || 'S0'}
                        revision={topic.revision_code || 'P01.01'}
                        cdeState={topic.cde_state || 'WIP'}
                      />
                    </td>
                    <td class="py-3 px-4 font-mono text-slate-300">
                      {topic.component_guids ? topic.component_guids.length : 0} GUID{topic.component_guids?.length === 1 ? '' : 's'}
                    </td>
                    <td class="py-3 px-4">
                      <span class="inline-flex items-center gap-1 text-slate-300 text-caption">
                        <Camera class="w-3 h-3 text-blue-400" />
                        <span>{topic.viewpoints_count || 1}</span>
                      </span>
                    </td>
                    <td class="py-3 px-4 text-right whitespace-nowrap">
                      <div class="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          on:click={() => openTopicDetails(topic)}
                          class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-50 transition-colors"
                          title="View topic discussion & viewpoints"
                        >
                          <Eye class="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          on:click={() => openTopicEdit(topic)}
                          class="p-1.5 rounded-lg text-slate-400 hover:text-blue-400 hover:bg-blue-950/30 transition-colors"
                          title="Edit topic"
                        >
                          <Pencil class="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          on:click={() => promptDeleteTopic(topic)}
                          class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                          title="Delete topic"
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
        <div class="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800/90 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div class="relative flex-1 w-full">
            <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              bind:value={artifactSearchQuery}
              placeholder="Filter BCF archives by filename or project..."
              class="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-accent"
            />
          </div>

          {#if selectedProjectId}
            <div class="flex items-center rounded-xl bg-slate-900 p-1 border border-slate-800 text-xs">
              <button
                type="button"
                on:click={() => (filterToSelectedProject = false)}
                class="px-2.5 py-1 rounded-lg font-medium transition-colors {!filterToSelectedProject
                  ? 'bg-slate-800 text-slate-50'
                  : 'text-slate-400 hover:text-slate-50'}"
              >
                All Projects
              </button>
              <button
                type="button"
                on:click={() => (filterToSelectedProject = true)}
                class="px-2.5 py-1 rounded-lg font-medium transition-colors {filterToSelectedProject
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
              class="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"
            ></div>
            Loading BCF artifacts…
          </div>
        {:else if displayedBcfArtifacts.length === 0}
          <div
            class="p-12 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl"
          >
            {filterToSelectedProject
              ? `No BCF reports found for ${currentProject?.name || "this project"}. Run an ARCH Compliance Audit to generate one.`
              : "No persisted BCF artifacts found matching your filter."}
          </div>
        {:else}
          <div class="overflow-x-auto rounded-xl border border-slate-800/80">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr
                  class="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-semibold uppercase tracking-wider text-micro"
                >
                  <th class="py-3 px-4 w-10">
                    <TableCheckbox
                      checked={allFilteredArtifactsSelected}
                      on:change={toggleSelectAllArtifacts}
                      title="Select all BCF artifacts"
                    />
                  </th>
                  <SortHeader column="id" sortField={artifactSortField} sortAsc={artifactSortAsc} onSort={toggleArtifactSort}>
                    ID
                  </SortHeader>
                  <th class="py-3 px-4">Project</th>
                  <SortHeader column="filename" sortField={artifactSortField} sortAsc={artifactSortAsc} onSort={toggleArtifactSort}>
                    Artifact / Filename
                  </SortHeader>
                  <SortHeader column="issue_count" sortField={artifactSortField} sortAsc={artifactSortAsc} onSort={toggleArtifactSort}>
                    Issues
                  </SortHeader>
                  <SortHeader column="byte_size" sortField={artifactSortField} sortAsc={artifactSortAsc} onSort={toggleArtifactSort}>
                    Size
                  </SortHeader>
                  <SortHeader column="created_at" sortField={artifactSortField} sortAsc={artifactSortAsc} onSort={toggleArtifactSort}>
                    Date
                  </SortHeader>
                  <th class="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each paginatedArtifacts as artifact}
                  <tr class="hover:bg-slate-900/60 transition-colors {selectedArtifactIds.includes(artifact.id) ? 'bg-blue-950/20' : ''}">
                    <td class="py-3 px-4 w-10">
                      <TableCheckbox
                        checked={selectedArtifactIds.includes(artifact.id)}
                        on:change={() => toggleSelectArtifact(artifact.id)}
                        ariaLabel={`Select artifact ${artifact.filename}`}
                      />
                    </td>
                    <td class="py-3 px-4 font-mono text-slate-500">#{artifact.id}</td>
                    <td class="py-3 px-4 font-medium text-slate-50">
                      {getProjectName(artifact.project_id)}
                    </td>
                    <td class="py-3 px-4">
                      <div
                        class="font-mono text-slate-300 truncate max-w-xs"
                        title={artifact.filename}
                      >
                        {artifact.filename}
                      </div>
                    </td>
                    <td class="py-3 px-4">
                      <span
                        class="inline-block px-2.5 py-0.5 rounded-full text-micro font-semibold border {artifact.issue_count > 0
                          ? 'bg-rose-950/60 text-rose-300 border-rose-800'
                          : 'bg-emerald-950/60 text-emerald-300 border-emerald-800'}"
                      >
                        {artifact.issue_count} issue{artifact.issue_count === 1 ? "" : "s"}
                      </span>
                    </td>
                    <td class="py-3 px-4 font-mono text-slate-400">
                      {formatBytes(artifact.byte_size)}
                    </td>
                    <td class="py-3 px-4 text-slate-400 whitespace-nowrap">
                      {formatDate(artifact.created_at)}
                    </td>
                    <td class="py-3 px-4 text-right">
                      <div class="inline-flex items-center justify-end gap-1.5">
                        {#if onSelectProjectForViewer}
                          <button
                            type="button"
                            on:click={() =>
                              onSelectProjectForViewer &&
                              onSelectProjectForViewer(
                                artifact.project_id,
                                undefined,
                                artifact.id
                              )}
                            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-900/40 hover:bg-emerald-800/60 text-emerald-300 border border-emerald-800 transition-colors"
                            title="Open 3D Viewer with this BCF Report"
                          >
                            <ScanEye class="w-3.5 h-3.5" />
                            View 3D
                          </button>
                        {/if}
                        <a
                          href={analyzeApi.getBcfArtifactUrl(artifact.id)}
                          download
                          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 transition-colors"
                          title="Download BCF 2.1 Zip"
                        >
                          <Download class="w-3.5 h-3.5" />
                          Zip
                        </a>
                        <button
                          type="button"
                          on:click={() => promptDeleteArtifact(artifact)}
                          class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                          title="Delete BCF archive"
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
      class="p-16 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl"
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
