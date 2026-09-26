<script lang="ts">
  import { onMount, untrack } from "svelte";
  import {
    FileText,
    Download,
    CheckCircle2,
    AlertTriangle,
    Clock,
    DollarSign,
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
    Network,
  } from "lucide-svelte";
  import { projectsApi, analyzeApi, bcfApi, rulesApi, graphApi } from "../lib/api";
  import Button from "../lib/components/ui/Button.svelte";
  import { authState } from "../lib/auth.svelte";
  import type { Project, AnalysisResult, BcfArtifact, BCFTopicResponse } from "../lib/types";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import BcfTopicEditModal from "../lib/components/BcfTopicEditModal.svelte";
  import BcfTopicDetailsModal from "../lib/components/BcfTopicDetailsModal.svelte";
  import BcfBulkEditModal from "../lib/components/BcfBulkEditModal.svelte";
  import ReportArtifactsTable from "../lib/components/ReportArtifactsTable.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import IsoGovernanceBadges from "../lib/components/IsoGovernanceBadges.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";
  import TabStrip, { type TabStripItem } from "../lib/components/TabStrip.svelte";
  import { Select, type SelectOption } from "../lib/components/ui";
  import Alert from "../lib/components/Alert.svelte";
  import { createTableState } from "../lib/tableState.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../lib/utils/errorLog";

  type ArtifactType = "bcf" | "pdf" | "csv";

  const reportTabs: TabStripItem[] = [
    { id: "live_bcf", label: "Live BCF 2.1 Topics" },
    { id: "artifacts", label: "BCF Zip Artifacts" },
    { id: "pdf_artifacts", label: "PDF Reports" },
    { id: "csv_artifacts", label: "CSV Exports" },
  ];

  const statusFilterOptions: SelectOption[] = [
    { value: "ALL", label: "All Statuses" },
    { value: "Open", label: "Open" },
    { value: "In Progress", label: "In Progress" },
    { value: "Resolved", label: "Resolved" },
    { value: "Closed", label: "Closed" },
  ];

  const priorityFilterOptions: SelectOption[] = [
    { value: "ALL", label: "All Priorities" },
    { value: "Critical", label: "Critical" },
    { value: "High", label: "High" },
    { value: "Normal", label: "Normal" },
    { value: "Low", label: "Low" },
  ];

  const cdeFilterOptions: SelectOption[] = [
    { value: "ALL", label: "All CDE States" },
    { value: "WIP", label: "WIP" },
    { value: "SHARED", label: "SHARED" },
    { value: "PUBLISHED", label: "PUBLISHED" },
    { value: "ARCHIVED", label: "ARCHIVED" },
  ];

  interface Props {
    initialProjectId?: number | null;
    onSelectProjectForViewer?:
      ((projectId: number, elementGuid?: string, bcfArtifactId?: number) => void) | undefined;
  }

  let { initialProjectId = null, onSelectProjectForViewer = undefined }: Props = $props();

  let projects: Project[] = $state([]);
  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  // Re-syncs when the header's project switcher changes initialProjectId
  // while this view is already mounted.
  $effect(() => {
    if (initialProjectId !== undefined && initialProjectId !== selectedProjectId) {
      selectedProjectId = initialProjectId;
      if (selectedProjectId) {
        loadReport();
        loadBcfTopics();
      } else {
        result = null;
        bcfTopics = [];
      }
    }
  });
  let result: AnalysisResult | null = null;
  let isLoading = false;
  let error = $state("");
  let errorLog: ErrorLogEntry[] = $state([]);

  // ARCH Report Artifacts -- BCF, PDF and CSV each get their own list, own
  // loading flag and own project filter, but share one delete-confirmation
  // flow and one table-state shape (BcfArtifact covers all three; it's the
  // generic report_artifacts row).
  let bcfArtifacts: BcfArtifact[] = $state([]);
  let pdfArtifacts: BcfArtifact[] = $state([]);
  let csvArtifacts: BcfArtifact[] = $state([]);
  let isBcfLoading = $state(false);
  let isPdfLoading = $state(false);
  let isCsvLoading = $state(false);
  let bcfFilterToSelected = $state(false);
  let pdfFilterToSelected = $state(false);
  let csvFilterToSelected = $state(false);
  let isDeleteArtifactModalOpen = $state(false);
  let artifactToDelete: { type: ArtifactType; artifact: BcfArtifact } | null = $state(null);
  let isBulkDeleteArtifactsModalOpen = $state(false);
  let bulkDeleteType: ArtifactType = $state("bcf");

  function artifactsFor(type: ArtifactType): BcfArtifact[] {
    return type === "bcf" ? bcfArtifacts : type === "pdf" ? pdfArtifacts : csvArtifacts;
  }

  function setArtifactsFor(type: ArtifactType, rows: BcfArtifact[]): void {
    if (type === "bcf") bcfArtifacts = rows;
    else if (type === "pdf") pdfArtifacts = rows;
    else csvArtifacts = rows;
  }

  function tableFor(type: ArtifactType) {
    return type === "bcf" ? bcfArtifactTable : type === "pdf" ? pdfArtifactTable : csvArtifactTable;
  }

  function filterToSelectedFor(type: ArtifactType): boolean {
    return type === "bcf" ? bcfFilterToSelected : type === "pdf" ? pdfFilterToSelected : csvFilterToSelected;
  }

  function setFilterToSelectedFor(type: ArtifactType, v: boolean): void {
    if (type === "bcf") bcfFilterToSelected = v;
    else if (type === "pdf") pdfFilterToSelected = v;
    else csvFilterToSelected = v;
  }

  // Artifact search, sort, paginate and select -- one table-state instance
  // per artifact type, each scoped to its own project-filter toggle.
  const bcfArtifactTable = createTableState<BcfArtifact, number>({
    rows: () =>
      bcfFilterToSelected && selectedProjectId
        ? bcfArtifacts.filter((a) => a.project_id === selectedProjectId)
        : bcfArtifacts,
    getId: (a) => a.id,
    searchFields: (a) => [a.filename, getProjectName(a.project_id)],
    initialSort: { field: "id", asc: false },
  });
  const pdfArtifactTable = createTableState<BcfArtifact, number>({
    rows: () =>
      pdfFilterToSelected && selectedProjectId
        ? pdfArtifacts.filter((a) => a.project_id === selectedProjectId)
        : pdfArtifacts,
    getId: (a) => a.id,
    searchFields: (a) => [a.filename, getProjectName(a.project_id)],
    initialSort: { field: "id", asc: false },
  });
  const csvArtifactTable = createTableState<BcfArtifact, number>({
    rows: () =>
      csvFilterToSelected && selectedProjectId
        ? csvArtifacts.filter((a) => a.project_id === selectedProjectId)
        : csvArtifacts,
    getId: (a) => a.id,
    searchFields: (a) => [a.filename, getProjectName(a.project_id)],
    initialSort: { field: "id", asc: false },
  });

  // Live BCF REST Topics
  let bcfTopics: BCFTopicResponse[] = $state([]);
  let isTopicsLoading = $state(false);
  let activeTab: "live_bcf" | "artifacts" | "pdf_artifacts" | "csv_artifacts" = $state("live_bcf");
  // Topic search, filter, sort, paginate and select.
  const topicTable = createTableState<BCFTopicResponse, string>({
    rows: () => bcfTopics || [],
    getId: (t) => t.guid,
    searchFields: (t) => [t.title, t.guid, t.description, t.assigned_to],
    filters: {
      status: (t, v) => (t.topic_status || "Open") === v,
      priority: (t, v) => (t.priority || "Normal") === v,
      cde: (t, v) => (t.cde_state || "WIP") === v,
    },
    initialSort: { field: "creation_date", asc: false },
  });

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

  // Projects and BCF artifacts are both fundamentally project-owned
  // resources -- an org never tags either directly, so "this org's
  // reports" always means "reports whose project belongs to this org"
  // (enforced server-side; see visible_project_rows / GET /analyze/bcf/list).
  // Re-fetch both whenever the active org changes, matching the guard
  // pattern in DashboardView: a slower response for a previously active org
  // must not resolve after (and overwrite) the current org's data.
  $effect(() => {
    const orgId = authState.activeOrganizationId;
    untrack(() => {
      loadReportArtifacts("bcf", orgId);
      loadReportArtifacts("pdf", orgId);
      loadReportArtifacts("csv", orgId);
      projectsApi.list({ organization_id: orgId }).then((data) => {
        if (authState.activeOrganizationId !== orgId) return;
        projects = data.projects || [];
      });
    });
  });

  onMount(async () => {
    if (selectedProjectId) {
      try {
        await Promise.all([loadReport(), loadBcfTopics()]);
      } catch {
        // ignore
      }
    }
  });

  // A fast double project-switch (via the header's global switcher) fires
  // loadReport/loadBcfTopics twice in a row; network responses aren't
  // guaranteed to arrive in request order, so a request token per function
  // makes a slower, stale response a no-op instead of letting it clobber a
  // newer one that already resolved.
  let reportLoadToken = 0;

  async function loadReport() {
    if (!selectedProjectId) return;
    const token = ++reportLoadToken;
    isLoading = true;
    try {
      const res = await analyzeApi.getResults(selectedProjectId, "architecture");
      if (token !== reportLoadToken) return;
      result = res;
    } catch {
      if (token !== reportLoadToken) return;
      result = null;
    } finally {
      if (token === reportLoadToken) isLoading = false;
    }
  }

  function setLoadingFor(type: ArtifactType, v: boolean): void {
    if (type === "bcf") isBcfLoading = v;
    else if (type === "pdf") isPdfLoading = v;
    else isCsvLoading = v;
  }

  async function loadReportArtifacts(
    type: ArtifactType,
    orgId: number | null = authState.activeOrganizationId,
  ) {
    setLoadingFor(type, true);
    try {
      const artifacts = await analyzeApi.listReportArtifacts(type, orgId);
      if (authState.activeOrganizationId !== orgId) return;
      setArtifactsFor(type, artifacts);
    } catch {
      if (authState.activeOrganizationId === orgId) setArtifactsFor(type, []);
    } finally {
      if (authState.activeOrganizationId === orgId) setLoadingFor(type, false);
    }
  }

  let bcfTopicsLoadToken = 0;

  async function loadBcfTopics() {
    if (!selectedProjectId) {
      bcfTopics = [];
      return;
    }
    const token = ++bcfTopicsLoadToken;
    isTopicsLoading = true;
    try {
      const topics = await bcfApi.listTopics(selectedProjectId);
      if (token !== bcfTopicsLoadToken) return;
      bcfTopics = topics;
    } catch {
      if (token !== bcfTopicsLoadToken) return;
      bcfTopics = [];
    } finally {
      if (token === bcfTopicsLoadToken) isTopicsLoading = false;
    }
  }

  function exportTopicsToCsv() {
    const target = topicTable.selectedCount ? topicTable.selectedRows : topicTable.sorted;
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
      topicTable.selectedIds.delete(topicToDelete!.guid);
      topicToDelete = null;
    } catch (err: any) {
      error = `Failed to delete topic: ${err.message}`;
      errorLog = [toErrorLogEntry(err, topicToDelete.guid)];
    }
  }

  async function confirmBulkDeleteTopics() {
    if (!topicTable.selectedCount || !selectedProjectId) return;
    try {
      await bcfApi.bulkDeleteTopics(selectedProjectId, topicTable.selectedIdList);
      bcfTopics = bcfTopics.filter((t) => !topicTable.selectedIds.has(t.guid));
      topicTable.clearSelection();
      isTopicBulkDeleteModalOpen = false;
    } catch (err: any) {
      error = `Failed to delete selected topics: ${err.message}`;
      errorLog = [toErrorLogEntry(err, `${topicTable.selectedIdList.length} topic(s)`)];
    }
  }

  function exportArtifactsToCsv(type: ArtifactType) {
    const table = tableFor(type);
    const target = table.selectedCount ? table.selectedRows : table.sorted;
    const headers = [
      "ID",
      "ProjectID",
      "ProjectName",
      "Ruleset",
      "User",
      "Filename",
      "Issues",
      "ByteSize",
      "CreatedAt",
    ];
    const rows = target.map((a) => [
      a.id,
      a.project_id,
      `"${getProjectName(a.project_id).replace(/"/g, '""')}"`,
      `"${(a.ruleset_name || "All Rules").replace(/"/g, '""')}"`,
      `"${(a.created_by_email || "").replace(/"/g, '""')}"`,
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
      `${type}_artifacts_export_${new Date().toISOString().substring(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // Built at click time, not render time: this list is rendered once when it
  // loads and can sit on screen for a while, but analyzeApi.getReportArtifactUrl
  // bakes in the auth token current at the moment it's called (a browser
  // navigation can't carry an Authorization header) -- see authToken.ts's
  // withAuthToken. A URL computed once up front would still download with
  // that original token even after it's expired.
  function downloadReportArtifact(type: ArtifactType, artifactId: number) {
    window.location.href = analyzeApi.getReportArtifactUrl(type, artifactId);
  }

  function promptDeleteArtifact(type: ArtifactType, artifact: BcfArtifact) {
    artifactToDelete = { type, artifact };
    isDeleteArtifactModalOpen = true;
  }

  async function confirmDeleteArtifact() {
    if (!artifactToDelete) return;
    const { type, artifact } = artifactToDelete;
    try {
      await analyzeApi.deleteReportArtifact(type, artifact.id);
      setArtifactsFor(type, artifactsFor(type).filter((a) => a.id !== artifact.id));
      tableFor(type).selectedIds.delete(artifact.id);
      artifactToDelete = null;
    } catch (err: any) {
      error = `Failed to delete ${type.toUpperCase()} artifact: ${err.message}`;
      errorLog = [toErrorLogEntry(err, `${type} artifact #${artifact.id}`)];
    }
  }

  function promptBulkDeleteArtifacts(type: ArtifactType) {
    bulkDeleteType = type;
    isBulkDeleteArtifactsModalOpen = true;
  }

  async function confirmBulkDeleteArtifacts() {
    const type = bulkDeleteType;
    const table = tableFor(type);
    if (!table.selectedCount) return;
    const targetIds = table.selectedIdList;
    const failures: ErrorLogEntry[] = [];
    const deletedIds = new Set<number>();
    for (const id of targetIds) {
      try {
        await analyzeApi.deleteReportArtifact(type, id);
        deletedIds.add(id);
      } catch (err: any) {
        failures.push(toErrorLogEntry(err, `${type} artifact #${id}`));
      }
    }
    setArtifactsFor(type, artifactsFor(type).filter((a) => !deletedIds.has(a.id)));
    table.clearSelection();
    isBulkDeleteArtifactsModalOpen = false;
    if (failures.length > 0) {
      errorLog = failures;
      error = `Could not delete ${failures.length} of ${targetIds.length} selected ${type.toUpperCase()} artifacts: ${failures[0].message}`;
    }
  }

  function getProjectName(projId: number): string {
    const p = projects.find((x) => x.id === projId);
    return p ? p.name : `Project #${projId}`;
  }

  let currentProject = $derived(projects.find((p) => p.id === selectedProjectId));
  // --- TOPIC COMPUTATIONS & SELECTION ---
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="Reports"
    title="Compliance Reports & Exports"
    subtitle="Generate, track, and download OpenBIM compliance audit deliverables in BCF 2.1, CSV, JSON, PDF, and W3C PROV-O RDF."
    icon={FolderArchive}
  >
    {#snippet actions()}
      {#if selectedProjectId}
        <Button
          variant="secondary"
          size="sm"
          class="flex items-center gap-2 border-border-interactive bg-surface-overlay text-xs font-medium text-fg-primary hover:bg-surface-hover"
          onclick={() => {
            window.open(graphApi.getProvOExportUrl(selectedProjectId), '_blank');
          }}
        >
          <Network class="h-4 w-4 text-accent" />
          <span>Export W3C PROV-O (.ttl)</span>
        </Button>
      {/if}
    {/snippet}
  </PageHeader>

  {#if error}
    <Alert
      type="error"
      message={error}
      errors={errorLog}
      logTitle="Reports Error Log"
      dismissible
      onDismiss={() => {
        error = "";
        errorLog = [];
      }}
    />
  {/if}

  {#if selectedProjectId}
    <!-- ═══ BCF Deliverables & Live Topics Hub ═══ -->
    <div class="space-y-4 rounded-2xl border border-border-default bg-surface-card/40 p-6">
      <div class="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <div class="flex items-center gap-2">
            <FolderArchive class="h-4 w-4 text-blue-400" />
            <h2 class="text-base font-bold tracking-tight text-fg-primary">
              buildingSMART BCF Collaboration Hub
            </h2>
            <span
              class="rounded-md border border-border-interactive bg-surface-overlay px-2 py-0.5 text-micro font-semibold text-fg-secondary"
            >
              {activeTab === "live_bcf"
                ? `${bcfTopics.length} Live Topics`
                : activeTab === "artifacts"
                  ? `${bcfArtifacts.length} Artifacts`
                  : activeTab === "pdf_artifacts"
                    ? `${pdfArtifacts.length} Artifacts`
                    : `${csvArtifacts.length} Artifacts`}
            </span>
          </div>
          <p class="mt-1 text-xs text-fg-muted">
            Bidirectional BCF REST API v2.1/v3.0 live topics exchange and persisted BCF zip
            deliverables with ISO 19650 governance tags.
          </p>
        </div>

        <!-- Tab & Action Controls -->
        <div class="flex shrink-0 flex-wrap items-center gap-2.5">
          <TabStrip
            tabs={reportTabs}
            active={activeTab}
            onSelect={(id) => (activeTab = id as any)}
            ariaLabel="Deliverables Views"
          />

          {#if activeTab === "live_bcf"}
            <button
              type="button"
              onclick={() => (isTopicCreateModalOpen = true)}
              class="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-blue-500"
            >
              <Plus class="h-3.5 w-3.5" />
              <span>Create Topic</span>
            </button>
          {/if}

          <button
            type="button"
            onclick={() => {
              if (activeTab === "live_bcf") loadBcfTopics();
              else if (activeTab === "artifacts") loadReportArtifacts("bcf");
              else if (activeTab === "pdf_artifacts") loadReportArtifacts("pdf");
              else loadReportArtifacts("csv");
            }}
            disabled={isTopicsLoading || isBcfLoading || isPdfLoading || isCsvLoading}
            class="rounded-xl border border-border-interactive bg-surface-overlay p-2 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary disabled:opacity-50"
            title="Refresh Deliverables"
          >
            <RefreshCw
              class="h-3.5 w-3.5 {isTopicsLoading || isBcfLoading || isPdfLoading || isCsvLoading
                ? 'animate-spin'
                : ''}"
            />
          </button>
        </div>
      </div>

      {#if activeTab === "live_bcf"}
        <!-- ── TAB 1: LIVE BCF 2.1 TOPICS ── -->

        <!-- Filters & Search Toolbar -->
        <div
          class="flex flex-col items-center gap-3 rounded-2xl border border-border-default/90 bg-surface-canvas/80 p-3.5 md:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
            <input
              type="text"
              bind:value={topicTable.search}
              placeholder="Search topics by title, GUID, assignee, or description..."
              class="w-full rounded-xl border border-border-default bg-surface-card py-2 pl-10 pr-4 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
            />
          </div>

          <div class="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <div class="w-36">
              <Select options={statusFilterOptions} bind:value={topicTable.filters.status} />
            </div>
            <div class="w-36">
              <Select options={priorityFilterOptions} bind:value={topicTable.filters.priority} />
            </div>
            <div class="w-36">
              <Select options={cdeFilterOptions} bind:value={topicTable.filters.cde} />
            </div>
          </div>
        </div>

        <!-- Bulk Action Toolbar -->
        <BulkActionBar
          selectedCount={topicTable.selectedCount}
          itemLabel="BCF topic"
          onClearSelection={() => topicTable.clearSelection()}
          onBulkEdit={() => (isTopicBulkEditModalOpen = true)}
          onBulkExport={exportTopicsToCsv}
          onBulkDelete={() => (isTopicBulkDeleteModalOpen = true)}
        />

        {#if isTopicsLoading && bcfTopics.length === 0}
          <LoadingState
            message={`Querying /api/bcf/v2.1/projects/${selectedProjectId}/topics...`}
          />
        {:else if topicTable.totalItems === 0}
          <div class="p-6">
            <EmptyState
              title={`No BCF topics match your criteria for ${currentProject?.name || "this project"}`}
              description="Create a topic or adjust filters to coordinate model findings."
              actionLabel={topicTable.hasActiveFilters ? "Reset Filters" : "+ Create BCF Topic"}
              onAction={() => {
                if (topicTable.hasActiveFilters) {
                  topicTable.reset();
                } else {
                  isTopicCreateModalOpen = true;
                }
              }}
            />
          </div>
        {:else}
          <div class="overflow-x-auto rounded-xl border border-border-default">
            <table class="w-full border-collapse text-left text-xs">
              <thead>
                <tr
                  class="border-b border-border-default bg-surface-canvas/60 text-micro font-semibold uppercase tracking-wider text-fg-muted"
                >
                  <th class="w-10 px-4 py-3">
                    <TableCheckbox
                      checked={topicTable.allFilteredSelected}
                      indeterminate={topicTable.someFilteredSelected}
                      onchange={() => topicTable.toggleSelectAll()}
                      title="Select all topics"
                    />
                  </th>
                  <SortHeader
                    column="guid"
                    sortField={topicTable.sortField}
                    sortAsc={topicTable.sortAsc}
                    onSort={(f) => topicTable.toggleSort(f)}
                  >
                    Topic GUID
                  </SortHeader>
                  <SortHeader
                    column="title"
                    sortField={topicTable.sortField}
                    sortAsc={topicTable.sortAsc}
                    onSort={(f) => topicTable.toggleSort(f)}
                  >
                    Title & Type
                  </SortHeader>
                  <SortHeader
                    column="topic_status"
                    sortField={topicTable.sortField}
                    sortAsc={topicTable.sortAsc}
                    onSort={(f) => topicTable.toggleSort(f)}
                  >
                    Status & Priority
                  </SortHeader>
                  <SortHeader
                    column="cde_state"
                    sortField={topicTable.sortField}
                    sortAsc={topicTable.sortAsc}
                    onSort={(f) => topicTable.toggleSort(f)}
                  >
                    ISO 19650 Governance
                  </SortHeader>
                  <th class="px-4 py-3">Elements</th>
                  <th class="px-4 py-3">Viewpoints</th>
                  <th class="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border-subtle">
                {#each topicTable.paginated as topic (topic.guid)}
                  <tr
                    class="transition-colors hover:bg-surface-hover {topicTable.isSelected(
                      topic.guid,
                    )
                      ? 'bg-surface-selected'
                      : ''}"
                  >
                    <td class="w-10 px-4 py-3">
                      <TableCheckbox
                        checked={topicTable.isSelected(topic.guid)}
                        onchange={() => topicTable.toggleSelect(topic.guid)}
                        ariaLabel={`Select topic ${topic.title}`}
                      />
                    </td>
                    <td class="px-4 py-3 font-mono text-caption text-fg-muted">
                      {topic.guid.substring(0, 8)}...
                    </td>
                    <td class="px-4 py-3">
                      <div class="font-medium text-fg-primary">{topic.title}</div>
                      <div class="text-micro text-fg-muted">
                        {topic.topic_type || "Clash / Compliance"}
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-1.5">
                        <SeverityBadge severity={topic.topic_status || "Open"} />
                        <span class="text-micro font-medium text-fg-muted">
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
                    <td class="px-4 py-3 font-mono text-fg-secondary">
                      {topic.component_guids ? topic.component_guids.length : 0} GUID{topic
                        .component_guids?.length === 1
                        ? ""
                        : "s"}
                    </td>
                    <td class="px-4 py-3">
                      <span class="inline-flex items-center gap-1 text-caption text-fg-secondary">
                        <Camera class="h-3 w-3 text-blue-400" />
                        <span>{topic.viewpoints_count || 1}</span>
                      </span>
                    </td>
                    <td class="whitespace-nowrap px-4 py-3 text-right">
                      <div class="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onclick={() => openTopicDetails(topic)}
                          class="rounded-lg bg-surface-overlay p-1.5 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
                          title="View topic discussion & viewpoints"
                        >
                          <Eye class="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onclick={() => openTopicEdit(topic)}
                          class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-accent"
                          title="Edit topic"
                        >
                          <Pencil class="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onclick={() => promptDeleteTopic(topic)}
                          class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-critical-bg/40 hover:text-critical"
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
            currentPage={topicTable.page}
            pageSize={topicTable.pageSize}
            totalItems={topicTable.totalItems}
            onPageChange={(p) => (topicTable.requestedPage = p)}
            onPageSizeChange={(size) => {
              topicTable.pageSize = size;
              topicTable.requestedPage = 1;
            }}
          />
        {/if}
      {:else if activeTab === "artifacts"}
        <!-- ── TAB 2: ARCHIVED BCF ZIP ARTIFACTS ── -->
        <ReportArtifactsTable
          artifacts={bcfArtifacts}
          tableState={bcfArtifactTable}
          typeLabel="BCF"
          downloadLabel="Zip"
          {projects}
          isLoading={isBcfLoading}
          {selectedProjectId}
          filterToSelectedProject={bcfFilterToSelected}
          onFilterToggle={(v) => (bcfFilterToSelected = v)}
          onDownload={(a) => downloadReportArtifact("bcf", a.id)}
          onDeleteOne={(a) => promptDeleteArtifact("bcf", a)}
          onBulkDelete={() => promptBulkDeleteArtifacts("bcf")}
          onBulkExport={() => exportArtifactsToCsv("bcf")}
          onViewIn3d={onSelectProjectForViewer
            ? (a) => onSelectProjectForViewer!(a.project_id, undefined, a.id)
            : undefined}
        />
      {:else if activeTab === "pdf_artifacts"}
        <!-- ── TAB 3: SAVED PDF REPORTS ── -->
        <ReportArtifactsTable
          artifacts={pdfArtifacts}
          tableState={pdfArtifactTable}
          typeLabel="PDF"
          downloadLabel="PDF"
          {projects}
          isLoading={isPdfLoading}
          {selectedProjectId}
          filterToSelectedProject={pdfFilterToSelected}
          onFilterToggle={(v) => (pdfFilterToSelected = v)}
          onDownload={(a) => downloadReportArtifact("pdf", a.id)}
          onDeleteOne={(a) => promptDeleteArtifact("pdf", a)}
          onBulkDelete={() => promptBulkDeleteArtifacts("pdf")}
          onBulkExport={() => exportArtifactsToCsv("pdf")}
        />
      {:else}
        <!-- ── TAB 4: SAVED CSV EXPORTS ── -->
        <ReportArtifactsTable
          artifacts={csvArtifacts}
          tableState={csvArtifactTable}
          typeLabel="CSV"
          downloadLabel="CSV"
          {projects}
          isLoading={isCsvLoading}
          {selectedProjectId}
          filterToSelectedProject={csvFilterToSelected}
          onFilterToggle={(v) => (csvFilterToSelected = v)}
          onDownload={(a) => downloadReportArtifact("csv", a.id)}
          onDeleteOne={(a) => promptDeleteArtifact("csv", a)}
          onBulkDelete={() => promptBulkDeleteArtifacts("csv")}
          onBulkExport={() => exportArtifactsToCsv("csv")}
        />
      {/if}
    </div>

    <!-- ═══ PDF Compliance Report ═══ -->
    <div class="space-y-4 rounded-2xl border border-border-default bg-surface-card/40 p-6">
      <div class="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <div class="flex items-center gap-2">
            <FileText class="h-4 w-4 text-accent" />
            <h2 class="text-base font-bold tracking-tight text-fg-primary">PDF Compliance Report</h2>
          </div>
          <p class="mt-1 text-xs text-fg-muted">
            A deterministic, database-driven report for {currentProject?.name || "this project"} —
            cover, executive summary, priority findings, findings register and full rule
            traceability, generated from the latest analysis run. No LLM is used.
          </p>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-2.5">
          <button
            type="button"
            onclick={() =>
              window.open(analyzeApi.getReportUrl(selectedProjectId!, "architecture", "html"), "_blank")}
            class="inline-flex items-center gap-1.5 rounded-xl border border-border-interactive bg-surface-overlay px-3.5 py-1.5 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
          >
            <Eye class="h-3.5 w-3.5" />
            <span>Preview</span>
          </button>
          <button
            type="button"
            onclick={() =>
              window.open(analyzeApi.getReportUrl(selectedProjectId!, "architecture", "pdf"), "_blank")}
            class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-accent-hover"
          >
            <Download class="h-3.5 w-3.5" />
            <span>Download PDF</span>
          </button>
        </div>
      </div>
    </div>
  {:else}
    <div
      class="rounded-2xl border border-dashed border-border-default p-16 text-center text-xs text-fg-muted"
    >
      Please select a project from the top header to generate and export compliance audit deliverables.
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
    selectedTopicGuids={topicTable.selectedIdList}
    onClose={() => (isTopicBulkEditModalOpen = false)}
    onBulkUpdated={() => {
      loadBcfTopics();
      topicTable.clearSelection();
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
    message={`Are you sure you want to delete ${topicTable.selectedCount} selected BCF topic(s)? This cannot be undone.`}
    confirmText="Delete Selected Topics"
    danger={true}
    onConfirm={confirmBulkDeleteTopics}
    onCancel={() => topicTable.clearSelection()}
  />
{/if}

<!-- Delete Single Report Artifact Modal (BCF, PDF or CSV) -->
<ConfirmModal
  bind:isOpen={isDeleteArtifactModalOpen}
  title={`Delete ${artifactToDelete?.type.toUpperCase() || ""} Report Artifact`}
  message={`Are you sure you want to delete ${artifactToDelete?.type.toUpperCase() || ""} report "${artifactToDelete?.artifact.filename || ""}"?`}
  confirmText="Delete Report"
  danger={true}
  onConfirm={confirmDeleteArtifact}
  onCancel={() => (artifactToDelete = null)}
/>

<!-- Bulk Delete Report Artifacts Modal (BCF, PDF or CSV) -->
<ConfirmModal
  bind:isOpen={isBulkDeleteArtifactsModalOpen}
  title={`Delete Selected ${bulkDeleteType.toUpperCase()} Reports`}
  message={`Are you sure you want to delete ${tableFor(bulkDeleteType).selectedCount} selected ${bulkDeleteType.toUpperCase()} report(s)?`}
  confirmText="Delete Selected Reports"
  danger={true}
  onConfirm={confirmBulkDeleteArtifacts}
  onCancel={() => tableFor(bulkDeleteType).clearSelection()}
/>
