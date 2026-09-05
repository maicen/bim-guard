<script lang="ts">
  import { run } from "svelte/legacy";

  import { onMount, untrack } from "svelte";
  import {
    Play,
    Download,
    Cpu,
    Activity,
    CheckCircle2,
    AlertTriangle,
    ShieldAlert,
    ScanEye,
    Search,
    RefreshCw,
    FileCode,
    Box,
    Layers,
    FileText,
    Upload,
    Info,
    Check,
    X,
    Sparkles,
    ShieldCheck,
    ExternalLink,
    ChevronRight,
    Copy,
    Building2,
    Compass,
    SlidersHorizontal,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
  } from "lucide-svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { isAbortError, analyzeApi, projectsApi, rulesApi } from "../lib/api";
  import type { ApiError, IssueBand, IssueSort, ResultPageQuery } from "../lib/api";
  import HoverCard from "../lib/components/HoverCard.svelte";
  import { describeMechanism } from "../lib/glossary";
  import type {
    AnalysisResult,
    Project,
    AuditIssue,
    AnalysisInputItem,
    RuleFolder,
  } from "../lib/types";
  import PipelineProgress from "../lib/components/PipelineProgress.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import { toasts } from "../lib/toast.svelte";
  import Modal from "../lib/components/Modal.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import { pipelineTracker, avgPipelineProgress } from "../lib/stores/activePipelines.svelte";

  interface Props {
    initialProjectId?: number | null;
    activeCategory?: "Piping" | "seismic";
    onSelectProjectForViewer: (
      projectId: number,
      elementGuid?: string,
      bcfArtifactId?: number,
    ) => void;
  }

  let {
    initialProjectId = null,
    activeCategory = "Piping",
    onSelectProjectForViewer,
  }: Props = $props();

  let projects: Project[] = $state([]);
  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  // Re-syncs when the header's project switcher changes initialProjectId
  // while this view is already mounted.
  $effect(() => {
    if (initialProjectId !== undefined && initialProjectId !== selectedProjectId) {
      selectedProjectId = initialProjectId;
      handleProjectChange();
    }
  });
  let selectedSlug: "corrosion" | "seismic" = $state("corrosion");
  let isRunning = $state(false);
  let error = $state("");
  let result: AnalysisResult | null = $state(null);
  let analysisInputs: AnalysisInputItem[] = $state([]);

  let categoryFolders: RuleFolder[] = $state([]);
  let isFoldersLoading = false;

  async function loadCategoryFolders(cat: "Piping" | "seismic") {
    isFoldersLoading = true;
    try {
      categoryFolders = await rulesApi.folders(cat);
    } catch (err) {
      categoryFolders = [];
      toasts.fromError(err, "Could not load rule folders for this category.");
    } finally {
      isFoldersLoading = false;
    }
  }

  // Options & Filters

  // Engine selector (PIPING only). SEISMIC runs the single Blue Halo kernel,
  // so a selector there would offer a choice of one.
  const PIPING_ENGINES = [
    { id: "GC", label: "GC-001", title: "Galvanic corrosion" },
    { id: "CC", label: "CC-001", title: "Crevice corrosion" },
    { id: "MC", label: "MC-001", title: "Microbiologically influenced corrosion" },
    { id: "MM", label: "MM-001", title: "Material-media compatibility" },
    { id: "XM", label: "XM-001", title: "Cross-material compatibility" },
  ] as const;
  let selectedEngines: string[] = $state(PIPING_ENGINES.map((e) => e.id));

  function toggleEngine(id: string) {
    selectedEngines = selectedEngines.includes(id)
      ? selectedEngines.filter((e) => e !== id)
      : [...selectedEngines, id];
    reloadAfterFilterChange();
  }
  let showLowRisk = $state(true);
  let isUploadModalOpen = $state(false);
  let uploadFile: File | null = $state(null);
  let isUploading = $state(false);
  let uploadSuccessMsg = $state("");
  let uploadErrorMsg = $state("");
  let copiedGuid = "";

  // Inspection Drawer/Modal state
  let inspectedIssue: AuditIssue | null = $state(null);

  let prevRelevantKey = $state("");

  onMount(async () => {
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
      if (selectedProjectId) {
        await Promise.all([fetchResults(), loadInputs()]);
      }
    } catch (err: any) {
      error = err.message || "Failed to load projects";
    }
  });

  async function loadInputs() {
    if (!selectedProjectId) return;
    try {
      analysisInputs = await projectsApi.getInputs(selectedProjectId);
    } catch (err) {
      analysisInputs = [];
      toasts.fromError(err, "Could not load the analysis inputs for this project.");
    }
  }

  // Findings table: server-side paging.
  //
  // The table used to hold the whole run -- 17 MB and 21,134 issues on Clinic
  // Plumbing -- and page through it in the browser. It now asks the backend
  // for one page at a time, so every control below is a query parameter
  // rather than a filter over an array that is already in memory.
  //
  // `result` still holds an AnalysisResult, but `audit_issues` is now just the
  // current page. `issue_stats` describes the whole run in every response, so
  // the stat cards read it exactly as before; `result.page.total_matching` is
  // the row count for the current filters.

  const PAGE_SIZE_OPTIONS = [50, 200, 500];

  let pageSize = $state(50);
  let pageIndex = $state(1);
  let searchTerm = $state("");
  let severityFilter = $state("all");
  let mechanismFilter = $state("all");
  let sortMode: IssueSort = $state("band_then_score");
  let isPageLoading = $state(false);
  /** Set after a rejected page query, so the table falls back to one request. */
  let pagingUnavailable = $state(false);
  let selectedIds = new SvelteSet<string>();

  /** Translate the toolbar into query parameters. */
  function buildPageQuery(): ResultPageQuery | undefined {
    if (pagingUnavailable) return undefined;

    const bands: IssueBand[] = [];
    if (severityFilter !== "all") {
      bands.push(severityFilter as IssueBand);
    } else if (!showLowRisk) {
      // Data-quality notes ride along: they report what could not be assessed
      // rather than a mild verdict, so they survive the low-risk toggle the
      // same way they always have.
      bands.push("critical", "high", "medium", "data_quality");
    }

    const mechanisms: string[] = [];
    if (mechanismFilter !== "all") {
      mechanisms.push(mechanismFilter);
    } else if (requestedEngines) {
      // The chips choose what runs and, in step, what is listed. The notes are
      // exempt from the chips for the reason above.
      mechanisms.push(...requestedEngines, "data_quality");
    }

    return {
      limit: pageSize,
      offset: (pageIndex - 1) * pageSize,
      bands: bands.length ? bands : undefined,
      mechanisms: mechanisms.length ? mechanisms : undefined,
      sort: sortMode,
      search: searchTerm.trim() || undefined,
    };
  }

  /** Get bands and include_data_quality for export, matching current filter state. */
  function getExportFilters(): { bands?: string[]; includeDataQuality?: boolean } {
    const bands: string[] = [];
    if (severityFilter !== "all") {
      bands.push(severityFilter);
    } else if (!showLowRisk) {
      bands.push("critical", "high", "medium", "data_quality");
    }

    // include_data_quality is true if data_quality is in bands or if no specific bands (all)
    const includeDataQuality =
      bands.length === 0 || bands.includes("data_quality");

    return {
      bands: bands.length ? bands : undefined,
      includeDataQuality: includeDataQuality ? true : false,
    };
  }

  // Lets an in-flight request be abandoned, either by the user or because they
  // switched project or filter while it was still going.
  let runController: AbortController | null = null;

  /**
   * Load one page of findings.
   *
   * `useCache: false` recomputes the run. That is what the Re-run button used
   * to do through POST /run; asking this endpoint instead runs the same
   * `run_analysis` call behind the same pipeline tracker -- so the SSE
   * progress feed is unaffected -- and answers with a page rather than the
   * entire result, which is the whole point of the change.
   */
  async function fetchPage({ useCache = true, isRun = false } = {}) {
    if (!selectedProjectId) return;
    // Nothing can match, so there is nothing to ask for; the table renders its
    // empty state from `emptyByConstruction` either way.
    if (emptyByConstruction && !isRun) {
      isPageLoading = false;
      return;
    }

    runController?.abort();
    const controller = new AbortController();
    runController = controller;

    if (isRun) {
      isRunning = true;
      error = "";
      // Registers with the global pipeline tracker so a user who navigates away
      // mid-run still sees progress in the header and gets a completion toast.
      // Only on an actual run: paging the table starts no pipeline, and
      // tracking one would show a phantom job in the global header.
      pipelineTracker.track(selectedProjectId, currentProject?.name || `Project ${selectedProjectId}`);
    } else {
      isPageLoading = true;
    }

    // The previous report is deliberately kept until the new one lands: if this
    // request fails, discarding it first would have left the user with nothing
    // but an error message. It is dimmed while the request is in flight.
    try {
      const next = await analyzeApi.getResults(
        selectedProjectId,
        selectedSlug,
        useCache,
        requestedEngines,
        controller.signal,
        buildPageQuery(),
      );
      if (runController !== controller) return; // superseded by a newer request
      result = next;
      // Selection is per page: the rows it referred to are gone.
      selectedIds.clear();
    } catch (err: any) {
      if (isAbortError(err)) return;
      if (runController !== controller) return;

      // A 422 means this client built a query the endpoint rejected, which is
      // a bug in the code above rather than anything the user did. Say so
      // loudly, then fall back to the unpaginated request so the table still
      // shows the findings instead of going blank.
      if ((err as ApiError)?.status === 422 && !pagingUnavailable) {
        console.error(
          "[AnalyzeView] the results endpoint rejected the page query; " +
            "falling back to an unpaginated request.",
          err,
        );
        pagingUnavailable = true;
        runController = null;
        isRunning = false;
        isPageLoading = false;
        await fetchPage({ useCache, isRun });
        return;
      }

      if (isRun) {
        error = err.message || "Analysis failed";
        toasts.fromError(err, "Analysis failed.");
      } else {
        // A miss here is the normal "no analysis has been run yet" case, not a
        // failure, so it stays quiet; a run surfaces real errors.
        result = null;
      }
    } finally {
      if (runController === controller) {
        runController = null;
        isRunning = false;
        isPageLoading = false;
      }
      pipelineTracker.untrack(selectedProjectId);
    }
  }

  /** Load page one. Kept under its old name for the call sites that predate paging. */
  async function fetchResults(useCache = true) {
    pageIndex = 1;
    await fetchPage({ useCache });
  }

  // Toggling three chips should be one request, not three. Page and sort
  // changes are deliberate single clicks and reload straight away.
  let filterTimer: ReturnType<typeof setTimeout> | null = null;

  function reloadAfterFilterChange() {
    pageIndex = 1;
    if (filterTimer) clearTimeout(filterTimer);
    filterTimer = setTimeout(() => {
      filterTimer = null;
      void fetchPage();
    }, 250);
  }

  function reloadNow() {
    if (filterTimer) {
      clearTimeout(filterTimer);
      filterTimer = null;
    }
    void fetchPage();
  }

  function goToPage(page: number) {
    pageIndex = page;
    reloadNow();
  }

  function setPageSize(size: number) {
    pageSize = size;
    pageIndex = 1;
    reloadNow();
  }

  function setSort(column: string) {
    sortMode = column === "score" ? "score_desc" : "band_then_score";
    pageIndex = 1;
    reloadNow();
  }

  async function handleRun(forceRecompute = false) {
    if (!selectedProjectId) return;
    pageIndex = 1;
    await fetchPage({ useCache: !forceRecompute, isRun: true });
  }

  function handleCancelRun() {
    runController?.abort();
    runController = null;
    isRunning = false;
    isPageLoading = false;
    toasts.info("Analysis cancelled.");
  }

  async function handleProjectChange() {
    runController?.abort();
    runController = null;
    isRunning = false;
    isPageLoading = false;
    error = "";
    result = null;
    pageIndex = 1;
    selectedIds.clear();
    await Promise.all([fetchPage(), loadInputs()]);
  }

  // Page-local selection.
  //
  // Selection covers the rows on screen. It cannot span the run without
  // holding 21,134 ids for a set the user never sees, and it is cleared on
  // every page change so a stale id can never reach an action.

  function isSelected(id: string): boolean {
    return selectedIds.has(id);
  }

  function toggleSelect(id: string) {
    if (selectedIds.has(id)) selectedIds.delete(id);
    else selectedIds.add(id);
  }

  function toggleSelectAllOnPage() {
    if (allOnPageSelected) {
      for (const issue of pageIssues) selectedIds.delete(issue.id);
    } else {
      for (const issue of pageIssues) selectedIds.add(issue.id);
    }
  }

  async function handleUploadIfc() {
    if (!selectedProjectId || !uploadFile) return;
    isUploading = true;
    uploadSuccessMsg = "";
    uploadErrorMsg = "";
    try {
      const res = await analyzeApi.uploadIfc(selectedProjectId, uploadFile);
      uploadSuccessMsg = `Successfully attached ${res.filename} (${res.size_bytes?.toLocaleString() || "0"} bytes). SHA-256: ${res.sha256?.slice(0, 16) || ""}…`;

      // Refresh project info
      const data = await projectsApi.list();
      projects = data.projects || [];
      uploadFile = null;
      // The success message carries the SHA-256 digest, which is the whole point
      // of showing it; a 1.5s auto-close dismissed it before it could be read.
      // The user closes the dialog when they are done with it.
      toasts.success(`Attached ${res.filename}.`, "IFC model uploaded");
    } catch (err: any) {
      uploadErrorMsg = err.message || "Upload failed";
    } finally {
      isUploading = false;
    }
  }

  function copyText(text: string) {
    navigator.clipboard.writeText(text);
    copiedGuid = text;
    setTimeout(() => {
      if (copiedGuid === text) copiedGuid = "";
    }, 2000);
  }

  /**
   * Download the run as CSV.
   *
   * The same URL the CSV button in the toolbar uses. This used to build a
   * spreadsheet from the issues held in memory, which with paging would have
   * exported whichever 50 rows happened to be on screen and called it the
   * report. The server renders the whole run from the same cached result.
   */
  function exportFindingsToCsv() {
    if (!selectedProjectId) return;
    const { bands, includeDataQuality } = getExportFilters();
    window.location.href = analyzeApi.getExportUrl(
      selectedProjectId,
      selectedSlug,
      "csv",
      requestedEngines,
      true,
      bands,
      includeDataQuality,
    );
  }
  run(() => {
    selectedSlug = activeCategory === "seismic" ? "seismic" : "corrosion";
  });
  run(() => {
    loadCategoryFolders(activeCategory);
  });
  // Leaving the category resets the selector, so a narrowed PIPING view never
  // silently hides findings after a route change.
  run(() => {
    if (activeCategory) selectedEngines = PIPING_ENGINES.map((e) => e.id);
  });
  // What the backend is asked to run. SEISMIC is a single kernel with nothing
  // to select between, so it sends no selection at all.
  let requestedEngines = $derived(activeCategory === "seismic" ? undefined : selectedEngines);
  // A run with no engine selected assesses nothing, so the button is disabled
  // rather than returning an empty audit that looks like a clean model.
  let engineSelectionEmpty = $derived(activeCategory !== "seismic" && selectedEngines.length === 0);
  let currentProject = $derived(projects.find((p) => p.id === selectedProjectId) || null);
  // Live progress echoed on the Run button itself, not just the progress
  // panel below — keeps attention anchored at the point of the click. Kept
  // through the pagination merge: it is the global pipeline feature, not part
  // of the table this merge replaced.
  let runProgress = $derived(
    avgPipelineProgress(pipelineTracker.tracked.find((t) => t.projectId === selectedProjectId)?.status),
  );
  // SEVERITY_WEIGHTS was dropped here: the severity ordering it fed moved to
  // the server with pagination, and the table no longer sorts client-side.

  function isDataQuality(issue: AuditIssue): boolean {
    return issue.mechanism === "data_quality" || issue.mechanism === "Data Quality";
  }

  /** The findings on screen. One page of the run, in the order the server cut it. */
  let pageIssues = $derived(result?.audit_issues || []);

  /** The window the server reported, absent while the fallback request is in use. */
  let pageWindow = $derived(result?.page ?? null);

  /**
   * The one filter combination that can select nothing.
   *
   * Asking for the Low band while Low verdicts are hidden is empty by
   * construction, and it was empty before this change too. It is answered here
   * rather than by a request, because "no bands" on the wire means "every
   * band", not "none".
   */
  let emptyByConstruction = $derived(!showLowRisk && severityFilter === "low");

  /** Rows matching the current filters across the whole run, not just this page. */
  let totalMatching = $derived(
    emptyByConstruction ? 0 : (pageWindow?.total_matching ?? pageIssues.length),
  );

  /** Findings in the run, verdicts and data-quality notes together. */
  let runTotalIssues = $derived(
    (result?.issue_stats?.total ?? 0) + (result?.issue_stats?.data_quality ?? 0),
  );

  let visibleIssues = $derived(emptyByConstruction ? [] : pageIssues);
  let selectedCount = $derived(selectedIds.size);
  let allOnPageSelected = $derived(
    visibleIssues.length > 0 && visibleIssues.every((issue) => selectedIds.has(issue.id)),
  );
  let someOnPageSelected = $derived(
    !allOnPageSelected && visibleIssues.some((issue) => selectedIds.has(issue.id)),
  );

  // The stat cards read the whole-run totals, which every response carries
  // regardless of the window, so they are unaffected by paging.
  let dataQualityCount = $derived(result?.issue_stats?.data_quality ?? 0);
</script>

<div class="space-y-6 pb-12">
  <!-- Top Navigation & Title Bar -->
  <div
    class="flex flex-col justify-between gap-4 border-b border-slate-800/80 pb-6 lg:flex-row lg:items-center"
  >
    <div>
      <div
        class="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-accent"
      >
        <span>Analysis Gateway</span>
        <span>•</span>
        <span class="text-slate-400">
          {activeCategory === "seismic"
            ? "Seismic Clearance (SB-001)"
            : "MEP Piping Corrosion (GC/CC/MC/MM/XM)"}
        </span>
      </div>
      <h1
        class="flex flex-wrap items-center gap-3 text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl"
      >
        <span
          >{activeCategory === "seismic"
            ? "Seismic Buffer & Bracing Audit"
            : "Piping System Corrosion Audit"}</span
        >
        <span
          class="inline-flex items-center rounded-md border px-2.5 py-0.5 font-mono text-xs font-semibold {activeCategory ===
          'seismic'
            ? 'border-purple-800/80 bg-purple-950/60 text-purple-300 shadow-sm'
            : 'border-amber-800/80 bg-amber-950/60 text-amber-300 shadow-sm'}"
        >
          Category: {activeCategory}
        </span>
        {#if result?.cached}
          <span
            class="inline-flex items-center gap-1 rounded-md border border-blue-800/80 bg-blue-950/80 px-2.5 py-0.5 text-caption font-semibold text-blue-300 shadow-sm"
          >
            <Sparkles class="h-3 w-3 text-blue-400" />
            Cached SHA-256
          </span>
        {/if}
      </h1>
      <p class="mt-1 max-w-3xl text-xs text-slate-400 sm:text-sm">
        {#if activeCategory === "seismic"}
          Execute verified Blue Halo Seismic Clearance (SB-001 / EN 1998-1 / DIN 4149) buffer volume
          and bracing audits.
        {:else}
          Execute verified Galvanic (GC-001), Crevice (CC-001), Microbiological (MC-001),
          Material-media (MM-001), and Cross-material (XM-001) piping compliance audits.
        {/if}
      </p>

      <!-- Active Rulesets within this category -->
      {#if categoryFolders.length > 0}
        <div class="mt-3 flex flex-wrap items-center gap-1.5">
          <span class="text-micro font-bold uppercase tracking-wider text-slate-500"
            >Active Rulesets:</span
          >
          {#each categoryFolders as folder (folder)}
            <span
              class="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-micro font-medium {activeCategory ===
              'seismic'
                ? 'border-purple-800/50 bg-purple-950/40 text-purple-300'
                : 'border-amber-800/50 bg-amber-950/40 text-amber-300'}"
              title={folder.description || folder.display_name}
            >
              <span>{folder.display_name}</span>
              <span class="opacity-60">({folder.rules.length})</span>
            </span>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Actions -->
    <div class="flex flex-wrap items-center gap-3">

      <!-- Run Action Button -->
      <button
        type="button"
        disabled={isRunning || !currentProject?.ifc_file_path || engineSelectionEmpty}
        title={engineSelectionEmpty
          ? "Select at least one engine to run"
          : "Run the audit against the selected engines"}
        onclick={() => handleRun(false)}
        class="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-blue-500/25 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:pointer-events-none disabled:opacity-50"
      >
        {#if isRunning}
          <RefreshCw class="h-3.5 w-3.5 animate-spin" />
          <span>Running Engine… {runProgress}%</span>
        {:else}
          <Play class="h-3.5 w-3.5 fill-current" />
          <span>Run Audit</span>
        {/if}
      </button>

      {#if isRunning}
        <button
          type="button"
          onclick={handleCancelRun}
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-900 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          title="Abandon the run in progress"
        >
          <span>Cancel</span>
        </button>
      {/if}

      <!-- Engine Selector (PIPING only) -->
      {#if activeCategory !== "seismic"}
        <div
          class="flex items-center gap-2 border-l border-slate-800 pl-1"
          role="group"
          aria-label="Corrosion engines"
        >
          <span class="text-micro font-bold uppercase tracking-wider text-slate-500">Engines</span>
          {#each PIPING_ENGINES as engine (engine.id)}
            {@const info = describeMechanism(engine.label)}
            <!-- Deciding which engines to run is a real choice, and the
                 five codes alone do not support it. The card says what each
                 kernel actually scores and which standard it answers to. -->
            <HoverCard
              side="bottom"
              align="center"
              width="w-80"
              focusable={false}
              title="{engine.label} — {engine.title}"
              subtitle={selectedEngines.includes(engine.id)
                ? "Included in this run"
                : "Excluded from this run"}
              showFooter={!!info?.reference}
            >
              {#snippet trigger()}
                <label
                  class="inline-flex cursor-pointer select-none items-center gap-1.5 rounded-lg border px-2.5 py-1 font-mono text-caption font-semibold transition-colors {selectedEngines.includes(
                    engine.id,
                  )
                    ? 'border-amber-800/80 bg-amber-950/60 text-amber-300'
                    : 'border-slate-800 bg-slate-900/60 text-slate-500 hover:text-slate-300'}"
                >
                  <input
                    type="checkbox"
                    class="sr-only"
                    checked={selectedEngines.includes(engine.id)}
                    onchange={() => toggleEngine(engine.id)}
                  />
                  {#if selectedEngines.includes(engine.id)}
                    <Check class="h-3 w-3" />
                  {/if}
                  <span>{engine.label}</span>
                </label>
              {/snippet}

              {info?.description || engine.title}

              {#snippet footer()}
                <span class="font-mono">{info?.reference}</span>
              {/snippet}
            </HoverCard>
          {/each}
        </div>
      {/if}

      <!-- Recompute (force uncached) -->
      {#if result}
        <button
          type="button"
          disabled={isRunning || !currentProject?.ifc_file_path || engineSelectionEmpty}
          onclick={() => handleRun(true)}
          title="Force uncached recomputation against the latest IFC digest"
          aria-label="Force uncached recomputation against the latest IFC digest"
          class="rounded-lg border border-slate-800 bg-slate-900/80 p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <RefreshCw class="h-3.5 w-3.5 {isRunning ? 'animate-spin' : ''}" />
        </button>
      {/if}
    </div>
  </div>

  <!-- Project Readiness & Lineage Section (Session A / B) -->
  {#if currentProject}
    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <!-- Project Metadata Card -->
      <div class="space-y-3 rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold uppercase tracking-wider text-slate-400"
            >Target Project</span
          >
          <span
            class="rounded px-2 py-0.5 text-micro font-semibold uppercase {currentProject.status ===
            'Active'
              ? 'border border-emerald-800/60 bg-emerald-950/60 text-emerald-400'
              : 'bg-slate-800 text-slate-400'}"
          >
            {currentProject.status}
          </span>
        </div>
        <div>
          <div class="truncate text-sm font-bold text-slate-50">
            {currentProject.name}
          </div>
          <div class="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
            <span>Jurisdiction: <strong>{currentProject.country}</strong></span>
            <span>•</span>
            <span>Type: <strong>{currentProject.analysis_type}</strong></span>
          </div>
        </div>
      </div>

      <!-- IFC Model Card & Lineage -->
      <div class="space-y-3 rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold uppercase tracking-wider text-slate-400"
            >IFC Model Lineage</span
          >
          {#if currentProject.ifc_file_path}
            <span
              class="rounded border border-emerald-800/60 bg-emerald-950/60 px-2 py-0.5 text-micro font-semibold uppercase text-emerald-400"
            >
              Model Ready
            </span>
          {:else}
            <span
              class="rounded border border-amber-800/60 bg-amber-950/60 px-2 py-0.5 text-micro font-semibold uppercase text-amber-400"
            >
              No Model Attached
            </span>
          {/if}
        </div>
        {#if currentProject.ifc_file_path}
          <div class="space-y-1 text-xs">
            <div
              class="truncate font-mono text-caption text-slate-300"
              title={currentProject.ifc_file_path}
            >
              {currentProject.ifc_file_path.split("/").pop()}
            </div>
            {#if currentProject.ifc_md5_hash}
              <div class="flex items-center gap-1.5 font-mono text-micro text-slate-500">
                <span>Digest: {currentProject.ifc_md5_hash.slice(0, 16)}…</span>
                <button
                  type="button"
                  onclick={() => copyText(currentProject?.ifc_md5_hash || "")}
                  title="Copy full digest"
                  aria-label="Copy full digest"
                  class="hover:text-slate-300"
                >
                  <Copy class="h-3 w-3" />
                </button>
              </div>
            {/if}
          </div>
          <div class="flex items-center gap-2 pt-1">
            <button
              type="button"
              onclick={() => onSelectProjectForViewer(currentProject.id)}
              class="inline-flex items-center gap-1 text-xs font-semibold text-accent transition-colors hover:text-blue-400"
            >
              <ScanEye class="h-3.5 w-3.5" />
              <span>Open 3D Viewer</span>
            </button>
            <span class="text-slate-700">•</span>
            <button
              type="button"
              onclick={() => (isUploadModalOpen = true)}
              class="text-xs text-slate-400 transition-colors hover:text-slate-50"
            >
              Replace Model
            </button>
          </div>
        {:else}
          <div class="text-xs text-amber-300/80">Attach an IFC model to run compliance checks.</div>
          <button
            type="button"
            onclick={() => (isUploadModalOpen = true)}
            class="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-400 hover:text-amber-300"
          >
            <Upload class="h-3.5 w-3.5" />
            <span>Upload IFC Model</span>
          </button>
        {/if}
      </div>

      <!-- Analysis Inputs (Standards & Client Docs) -->
      <div class="space-y-3 rounded-2xl border border-slate-800/80 bg-slate-900/40 p-4">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold uppercase tracking-wider text-slate-400"
            >Linked Standards &amp; Inputs</span
          >
          <span class="font-mono text-xs font-bold text-slate-300"
            >{analysisInputs.length} linked</span
          >
        </div>
        {#if analysisInputs.length > 0}
          <div class="flex max-h-16 flex-wrap gap-1.5 overflow-y-auto pr-1">
            {#each analysisInputs as inp (inp)}
              <span
                class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-micro font-medium {inp.kind ===
                'standard'
                  ? 'border border-indigo-800/60 bg-indigo-950/60 text-indigo-300'
                  : 'border border-teal-800/60 bg-teal-950/60 text-teal-300'}"
              >
                {inp.label}
              </span>
            {/each}
          </div>
        {:else}
          <div class="text-xs text-slate-500">Default regulatory rulepacks will be evaluated.</div>
        {/if}
        <div
          class="flex items-center gap-1.5 border-t border-slate-800/60 pt-1 text-micro text-slate-400"
        >
          <span
            class="inline-flex items-center gap-1 rounded border border-blue-800/60 bg-blue-950/60 px-1.5 py-0.5 font-semibold text-blue-300"
          >
            <ShieldCheck class="h-3 w-3 text-blue-400" />
            bSDD Verified
          </span>
          <span
            class="inline-flex items-center gap-1 rounded border border-amber-800/60 bg-amber-950/60 px-1.5 py-0.5 font-semibold text-amber-300"
          >
            <CheckCircle2 class="h-3 w-3 text-amber-400" />
            IDS 1.0 Compliant
          </span>
        </div>
      </div>
    </div>
  {/if}

  <!-- Error Alerts -->
  {#if error}
    <div
      class="flex items-center gap-3 rounded-2xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300"
    >
      <ShieldAlert class="h-5 w-5 shrink-0 text-rose-400" />
      <div>
        <strong class="font-bold">Execution Error:</strong>
        {error}
      </div>
    </div>
  {/if}

  <!-- Live 6-Stage Pipeline Progress -->
  {#if selectedProjectId && isRunning}
    <PipelineProgress projectId={selectedProjectId} />
  {/if}

  <!-- Results Section. While a run is in flight the previous report stays on
       screen, dimmed and inert, so a failed run does not leave the user with
       nothing. -->
  {#if result}
    <div
      class="{isRunning ? 'pointer-events-none opacity-40' : ''} transition-opacity duration-200"
    >
      <!-- Demo Mode Notice -->
      {#if result.compliance_is_demo}
        <div
          class="flex items-center gap-2.5 rounded-2xl border border-amber-800/70 bg-amber-950/40 p-4 text-xs text-amber-300"
        >
          <AlertTriangle class="h-4 w-4 shrink-0 text-amber-400" />
          <span
            ><strong>Demo Compliance Mode:</strong> Results are generated from demonstration test cases.</span
          >
        </div>
      {/if}

      <!-- Data Quality Doctrine Notice -->
      {#if dataQualityCount > 0}
        <div
          class="flex items-start gap-3 rounded-2xl border border-blue-800/70 bg-blue-950/40 p-4 text-xs text-blue-200 shadow-sm"
        >
          <Info class="mt-0.5 h-4 w-4 shrink-0 text-blue-400" />
          <div>
            <strong class="font-bold text-slate-50">White Box Data-Quality Doctrine:</strong>
            <span>
              {dataQualityCount} unassessed service elements are explicitly reported below as
              <strong>Data Quality</strong> findings (assigned to the BIM Coordinator) rather than fabricating
              a false compliance pass.
            </span>
          </div>
        </div>
      {/if}

      <!-- Executive KPI Statistics Grid -->
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm">
          <div class="text-caption font-semibold uppercase tracking-wider text-slate-400">
            Total Findings
          </div>
          <div class="mt-1 text-2xl font-bold text-slate-50">
            {result.issue_stats.total}
          </div>
          <div class="mt-0.5 text-micro text-slate-500">Non-compliant items</div>
        </div>
        <div class="rounded-2xl border border-red-900/40 bg-red-950/30 p-4 shadow-sm">
          <div class="text-caption font-semibold uppercase tracking-wider text-red-300">
            Critical
          </div>
          <div class="mt-1 text-2xl font-bold text-red-400">
            {result.issue_stats.critical}
          </div>
          <div class="mt-0.5 text-micro text-red-400/60">Immediate intervention</div>
        </div>
        <div class="rounded-2xl border border-orange-900/40 bg-orange-950/30 p-4 shadow-sm">
          <div class="text-caption font-semibold uppercase tracking-wider text-orange-300">
            High Risk
          </div>
          <div class="mt-1 text-2xl font-bold text-orange-400">
            {result.issue_stats.high}
          </div>
          <div class="mt-0.5 text-micro text-orange-400/60">Mandatory remediation</div>
        </div>
        <div class="rounded-2xl border border-yellow-900/40 bg-yellow-950/30 p-4 shadow-sm">
          <div class="text-caption font-semibold uppercase tracking-wider text-yellow-300">
            Medium Risk
          </div>
          <div class="mt-1 text-2xl font-bold text-yellow-400">
            {result.issue_stats.medium}
          </div>
          <div class="mt-0.5 text-micro text-yellow-400/60">Recommended mitigation</div>
        </div>
        <div class="rounded-2xl border border-emerald-900/40 bg-emerald-950/30 p-4 shadow-sm">
          <div class="text-caption font-semibold uppercase tracking-wider text-emerald-300">
            Low Risk
          </div>
          <div class="mt-1 text-2xl font-bold text-emerald-400">
            {result.issue_stats.low}
          </div>
          <div class="mt-0.5 text-micro text-emerald-400/60">Minor tolerance variance</div>
        </div>
        <div class="rounded-2xl border border-indigo-900/40 bg-indigo-950/30 p-4 shadow-sm">
          <div class="text-caption font-semibold uppercase tracking-wider text-indigo-300">
            Data Quality
          </div>
          <div class="mt-1 text-2xl font-bold text-indigo-300">
            {dataQualityCount}
          </div>
          <div class="mt-0.5 text-micro text-indigo-300/60">Unassessed mechanisms</div>
        </div>
      </div>

      <!-- Findings Table & Export Controls -->
      <div class="space-y-5 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
        <!-- Toolbar Header -->
        <div class="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h2 class="flex items-center gap-2 text-base font-bold tracking-tight text-slate-50">
              <span>Audit Findings</span>
              <span class="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                {totalMatching.toLocaleString()} of {runTotalIssues.toLocaleString()}
              </span>
              {#if isPageLoading}
                <span class="inline-flex items-center gap-1 text-caption text-slate-500">
                  <RefreshCw class="h-3 w-3 animate-spin" />
                  <span>Loading…</span>
                </span>
              {/if}
            </h2>
            <p class="mt-0.5 text-xs text-slate-400">
              Component compliance verdicts, authoritative citations, and actionable engineering
              mitigations.
            </p>
          </div>

          <!-- Multi-Format Export Actions (Session E) -->
          <div class="flex items-center gap-2">
            {#if selectedProjectId}
              {@const exportFilters = getExportFilters()}
              <a
                href={analyzeApi.getExportUrl(
                  selectedProjectId,
                  selectedSlug,
                  "bcf",
                  requestedEngines,
                  true,
                  exportFilters.bands,
                  exportFilters.includeDataQuality,
                )}
                class="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:scale-[1.02] hover:bg-accent-hover"
                title="Download standard OpenBIM BCF 2.1 archive for Revit, Solibri, and Navisworks"
              >
                <Download class="h-3.5 w-3.5" />
                <span>Export BCF 2.1</span>
              </a>
              <a
                href={analyzeApi.getExportUrl(
                  selectedProjectId,
                  selectedSlug,
                  "csv",
                  requestedEngines,
                  true,
                  exportFilters.bands,
                  exportFilters.includeDataQuality,
                )}
                class="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                title="Download tabulated audit spreadsheet with lineage and citations"
              >
                <Download class="h-3.5 w-3.5" />
                <span>CSV</span>
              </a>
              <a
                href={analyzeApi.getExportUrl(
                  selectedProjectId,
                  selectedSlug,
                  "json",
                  requestedEngines,
                  true,
                  exportFilters.bands,
                  exportFilters.includeDataQuality,
                )}
                class="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                title="Download structured machine-readable JSON analysis report"
              >
                <Download class="h-3.5 w-3.5" />
                <span>JSON</span>
              </a>
            {/if}
          </div>
        </div>

        <!-- Filters & Search Bar -->
        <div class="grid grid-cols-1 gap-3 pt-2 sm:grid-cols-12">
          <!-- Search Input -->
          <div class="relative sm:col-span-6">
            <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              oninput={(e) => {
                searchTerm = (e.currentTarget as HTMLInputElement).value;
                reloadAfterFilterChange();
              }}
              placeholder="Search findings by rule, GUID, title, or citation (e.g. NASA-STD, EN 1998)…"
              class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>

          <!-- Severity Filter -->
          <div class="sm:col-span-3">
            <select
              value={severityFilter}
              onchange={(e) => {
                severityFilter = (e.currentTarget as HTMLSelectElement).value;
                reloadAfterFilterChange();
              }}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="data_quality">Data Quality Only</option>
            </select>
          </div>

          <!-- Mechanism Filter -->
          <div class="sm:col-span-3">
            <select
              value={mechanismFilter}
              onchange={(e) => {
                mechanismFilter = (e.currentTarget as HTMLSelectElement).value;
                reloadAfterFilterChange();
              }}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="all">All Mechanisms</option>
              {#if selectedSlug === "corrosion"}
                <option value="GC">GC-001 Galvanic</option>
                <option value="CC">CC-001 Crevice</option>
                <option value="MC">MC-001 Microbiological</option>
                <option value="MM">MM-001 Material-media</option>
                <option value="XM">XM-001 Cross-material</option>
              {:else}
                <option value="SB">SB-001 Seismic Halo</option>
              {/if}
              <option value="data_quality">Data Quality</option>
            </select>
          </div>
        </div>

        <!-- Low Risk Visibility Toggle -->
        <div class="flex items-center justify-between px-1 text-xs text-slate-400">
          <label class="flex cursor-pointer select-none items-center gap-2">
            <input
              type="checkbox"
              checked={showLowRisk}
              onchange={(e) => {
                showLowRisk = (e.currentTarget as HTMLInputElement).checked;
                reloadAfterFilterChange();
              }}
              class="h-3.5 w-3.5 rounded border-slate-700 bg-slate-900 text-accent focus:ring-0"
            />
            <span>Include Low Severity verdicts in list</span>
          </label>
          <span class="text-caption text-slate-500">
            {totalMatching.toLocaleString()} matching {totalMatching === 1 ? "finding" : "findings"}
          </span>
        </div>

        <!-- Bulk Actions Bar -->
        <BulkActionBar
          selectedCount={selectedCount}
          itemLabel="finding"
          onClearSelection={() => selectedIds.clear()}
          onBulkExport={exportFindingsToCsv}
          onBulkDelete={null}
          onBulkEdit={null}
        />

        <!-- Tabular Findings Table -->
        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/50">
          {#if totalMatching === 0}
            <div class="p-12 text-center text-xs text-slate-500">
              No compliance issues match your selected filters.
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs text-slate-300">
                <thead
                  class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
                >
                  <tr>
                    <th class="w-10 px-4 py-3.5">
                      <input
                        type="checkbox"
                        checked={allOnPageSelected}
                        indeterminate={someOnPageSelected}
                        onchange={() => toggleSelectAllOnPage()}
                        class="h-4 w-4 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent focus:ring-accent"
                        title="Select every finding on this page"
                      />
                    </th>
                    <SortHeader
                      column="band"
                      sortField={sortMode === "score_desc" ? "score" : "band"}
                      sortAsc={false}
                      onSort={setSort}
                      customClass="px-4 py-3.5"
                    >
                      Severity
                    </SortHeader>
                    <th
                      class="px-4 py-3.5 text-caption font-semibold uppercase tracking-wider text-slate-400"
                    >
                      Rule &amp; Mechanism
                    </th>
                    <th
                      class="px-4 py-3.5 text-caption font-semibold uppercase tracking-wider text-slate-400"
                    >
                      Element GUID
                    </th>
                    <th
                      class="px-4 py-3.5 text-caption font-semibold uppercase tracking-wider text-slate-400"
                    >
                      Finding &amp; Citations
                    </th>
                    <SortHeader
                      column="score"
                      sortField={sortMode === "score_desc" ? "score" : "band"}
                      sortAsc={false}
                      onSort={setSort}
                      align="center"
                      customClass="px-4 py-3.5"
                    >
                      Score / Clearance
                    </SortHeader>
                    <th class="px-4 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60">
                  {#each visibleIssues as issue (issue.id)}
                    {@const isDq = isDataQuality(issue)}
                    <tr
                      class="group transition-colors hover:bg-slate-900/60 {isSelected(issue.id)
                        ? 'bg-blue-950/20'
                        : ''}"
                    >
                      <!-- Row Checkbox -->
                      <td class="w-10 px-4 py-3.5 align-top">
                        <input
                          type="checkbox"
                          checked={isSelected(issue.id)}
                          onchange={() => toggleSelect(issue.id)}
                          class="h-4 w-4 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent focus:ring-accent"
                        />
                      </td>

                      <!-- Severity Band Tag -->
                      <td class="whitespace-nowrap px-4 py-3.5 align-top">
                        {#if isDq}
                          <span
                            class="inline-block rounded-md border border-slate-700 bg-slate-800 px-2.5 py-0.5 text-micro font-semibold uppercase text-slate-300"
                          >
                            Data Quality
                          </span>
                        {:else if issue.band === "critical"}
                          <span
                            class="inline-block rounded-md border border-red-800/80 bg-red-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-red-400 shadow-sm"
                          >
                            Critical
                          </span>
                        {:else if issue.band === "high"}
                          <span
                            class="inline-block rounded-md border border-orange-800/80 bg-orange-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-orange-400 shadow-sm"
                          >
                            High
                          </span>
                        {:else if issue.band === "medium"}
                          <span
                            class="inline-block rounded-md border border-yellow-800/80 bg-yellow-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-yellow-400 shadow-sm"
                          >
                            Medium
                          </span>
                        {:else}
                          <span
                            class="inline-block rounded-md border border-emerald-800/80 bg-emerald-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-emerald-400 shadow-sm"
                          >
                            Low
                          </span>
                        {/if}
                      </td>

                      <!-- Rule & Mechanism -->
                      <td class="px-4 py-3.5 align-top font-mono">
                        <div class="text-xs font-bold text-slate-50">
                          {issue.rule_id}
                        </div>
                        <div class="mt-0.5 text-micro text-slate-400">
                          {issue.mechanism}
                        </div>
                      </td>

                      <!-- Element GUID -->
                      <td class="px-4 py-3.5 align-top">
                        <div
                          class="flex items-center gap-1.5 font-mono text-caption text-slate-300"
                        >
                          <span class="max-w-[140px] truncate" title={issue.element_id}
                            >{issue.element_id}</span
                          >
                          <button
                            type="button"
                            onclick={() => copyText(issue.element_id)}
                            class="text-slate-500 transition-colors hover:text-slate-50"
                            title="Copy GUID"
                            aria-label="Copy GUID"
                          >
                            <Copy class="h-3 w-3" />
                          </button>
                        </div>
                        {#if issue.details?.ifc_type}
                          <div class="mt-0.5 font-mono text-micro text-slate-500">
                            {issue.details.ifc_type}
                          </div>
                        {/if}
                      </td>

                      <!-- Finding, Mitigation, & Citations -->
                      <td class="max-w-md px-4 py-3.5 align-top">
                        <div class="font-semibold text-slate-100">
                          {issue.title}
                        </div>
                        {#if issue.mitigation}
                          <div class="mt-1 line-clamp-2 text-caption text-slate-400">
                            {issue.mitigation}
                          </div>
                        {/if}

                        <!-- Real Citations -->
                        {#if issue.citations && issue.citations.length > 0}
                          <div class="mt-2 flex flex-wrap items-center gap-1.5">
                            {#each issue.citations as cit (cit)}
                              <span
                                class="inline-flex items-center gap-1 rounded border border-indigo-900/60 bg-slate-900 px-2 py-0.5 text-micro font-medium text-indigo-300"
                                title={cit.reason}
                              >
                                <FileText class="h-2.5 w-2.5 opacity-70" />
                                <span>{cit.standard} {cit.clause}</span>
                              </span>
                            {/each}
                          </div>
                        {/if}
                      </td>

                      <!-- Score or Clearance Depth -->
                      <td class="px-4 py-3.5 text-center align-top font-mono">
                        {#if isDq}
                          <span class="text-caption text-slate-500">N/A</span>
                        {:else if issue.score !== undefined && issue.score > 0}
                          <div class="text-xs font-bold text-slate-50">
                            {issue.score.toFixed(2)}
                          </div>
                          <div class="text-nano text-slate-500">Risk Score</div>
                        {:else if issue.details?.intrusion_depth_mm !== undefined}
                          <div class="text-xs font-bold text-red-400">
                            {issue.details.intrusion_depth_mm} mm
                          </div>
                          <div class="text-nano text-slate-500">Clash Intrusion</div>
                        {:else}
                          <span class="text-caption text-slate-500">-</span>
                        {/if}
                      </td>

                      <!-- Action Buttons -->
                      <td class="space-x-1.5 whitespace-nowrap px-4 py-3.5 text-right align-top">
                        <button
                          type="button"
                          onclick={() => (inspectedIssue = issue)}
                          class="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                        >
                          <span>Details</span>
                        </button>

                        {#if selectedProjectId && issue.element_id}
                          <button
                            type="button"
                            onclick={() =>
                              onSelectProjectForViewer(selectedProjectId!, issue.element_id)}
                            class="inline-flex items-center gap-1 rounded-lg bg-accent/20 px-2.5 py-1 text-xs font-semibold text-accent transition-colors hover:bg-accent/30 hover:text-blue-300"
                          >
                            <ScanEye class="h-3.5 w-3.5" />
                            <span>3D</span>
                          </button>
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>

            <TablePagination
              currentPage={pageIndex}
              {pageSize}
              totalItems={totalMatching}
              pageSizeOptions={PAGE_SIZE_OPTIONS}
              onPageChange={goToPage}
              onPageSizeChange={setPageSize}
            />
          {/if}
        </div>
      </div>
    </div>
  {:else if !isRunning}
    <div
      class="space-y-3 rounded-2xl border border-dashed border-slate-800 p-16 text-center text-xs text-slate-500"
    >
      <div
        class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900 text-slate-400"
      >
        <Compass class="h-6 w-6" />
      </div>
      <div>
        <div class="text-sm font-bold text-slate-50">No Analysis Run Loaded</div>
        <div class="mx-auto mt-1 max-w-sm text-xs text-slate-400">
          Select an OpenBIM project above and click <strong>"Run Audit"</strong>
          to compute compliance across corrosion engines or Blue Halo seismic clearance envelopes.
        </div>
      </div>
    </div>
  {/if}
</div>

<!-- Detailed Issue Inspection Modal / Drawer -->
{#if inspectedIssue}
  {@const isDq = isDataQuality(inspectedIssue)}
  <Modal
    isOpen={true}
    title={inspectedIssue.title}
    subtitle={`${inspectedIssue.id} · ${inspectedIssue.rule_id}`}
    maxWidth="max-w-2xl"
    onClose={() => (inspectedIssue = null)}
  >
    {#snippet headerExtra()}
      <SeverityBadge severity={isDq ? "data_quality" : inspectedIssue.band} />
    {/snippet}

    <div class="space-y-6">
      <!-- Title & Mechanism -->
      <!-- The title now lives in the dialog header, so only the mechanism
             needs restating here. -->
      <p class="text-xs text-slate-400">
        Mechanism: <strong class="text-slate-200">{inspectedIssue.mechanism}</strong>
      </p>

      <!-- Element Context Card -->
      <div class="space-y-2 rounded-xl border border-slate-800/80 bg-slate-950/60 p-4">
        <div class="text-xs font-bold uppercase tracking-wider text-slate-400">
          Target IFC Element
        </div>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span class="text-slate-500">GlobalId (GUID):</span>
            <div class="mt-0.5 flex items-center gap-1.5 font-mono text-slate-200">
              <span class="truncate">{inspectedIssue.element_id}</span>
              <button
                type="button"
                onclick={() => copyText(inspectedIssue?.element_id || "")}
                title="Copy GUID"
                aria-label="Copy GUID"
                class="text-slate-400 hover:text-slate-50"
              >
                <Copy class="h-3 w-3" />
              </button>
            </div>
          </div>
          {#if inspectedIssue.assignee_role}
            <div>
              <span class="text-slate-500">Assigned Resolution Role:</span>
              <div class="mt-0.5 font-semibold text-slate-200">
                {inspectedIssue.assignee_role}
              </div>
            </div>
          {/if}
        </div>
      </div>

      <!-- Description & Mitigations -->
      {#if inspectedIssue.description}
        <div class="space-y-1">
          <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">
            Finding Description
          </h4>
          <p
            class="rounded-xl border border-slate-800/60 bg-slate-950/40 p-3 text-xs text-slate-300"
          >
            {inspectedIssue.description}
          </p>
        </div>
      {/if}

      {#if inspectedIssue.mitigation}
        <div class="space-y-1">
          <h4 class="text-xs font-bold uppercase tracking-wider text-emerald-400">
            Engineering Mitigation Guidance
          </h4>
          <p
            class="rounded-xl border border-emerald-800/40 bg-emerald-950/30 p-3 text-xs text-emerald-200"
          >
            {inspectedIssue.mitigation}
          </p>
        </div>
      {/if}

      <!-- Standards Cited (White Box Audit Trail) -->
      {#if inspectedIssue.citations && inspectedIssue.citations.length > 0}
        <div class="space-y-2">
          <h4 class="text-xs font-bold uppercase tracking-wider text-indigo-400">
            White Box Audit Citations
          </h4>
          <div class="space-y-2">
            {#each inspectedIssue.citations as cit (cit)}
              <div class="rounded-xl border border-indigo-800/40 bg-indigo-950/20 p-3 text-xs">
                <div class="flex items-center gap-1.5 font-bold text-indigo-300">
                  <FileText class="h-3.5 w-3.5" />
                  <span>{cit.standard} — {cit.clause}</span>
                </div>
                {#if cit.reason}
                  <div class="mt-1 text-caption text-slate-300">
                    {cit.reason}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Raw Metadata Details -->
      {#if inspectedIssue.details && Object.keys(inspectedIssue.details).length > 0}
        <div class="space-y-1">
          <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">
            Metadata Parameters
          </h4>
          <pre
            class="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-caption text-slate-400">{JSON.stringify(
              inspectedIssue.details,
              null,
              2,
            )}</pre>
        </div>
      {/if}
    </div>

    {#snippet footer()}
      <button
        type="button"
        onclick={() => (inspectedIssue = null)}
        class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
      >
        Close
      </button>

      {#if selectedProjectId && inspectedIssue?.element_id}
        <button
          type="button"
          onclick={() => {
            const elId = inspectedIssue?.element_id;
            inspectedIssue = null;
            if (selectedProjectId && elId) {
              onSelectProjectForViewer(selectedProjectId, elId);
            }
          }}
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent-hover"
        >
          <ScanEye class="h-4 w-4" />
          <span>Isolate in 3D Viewer</span>
        </button>
      {/if}
    {/snippet}
  </Modal>
{/if}

<!-- IFC Upload Modal -->
{#if isUploadModalOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm duration-200 animate-in fade-in"
  >
    <div
      class="w-full max-w-md space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between">
        <h3 class="text-base font-bold text-slate-50">Upload IFC Model</h3>
        <button
          type="button"
          onclick={() => (isUploadModalOpen = false)}
          class="text-slate-400 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <p class="text-xs text-slate-400">
        Attach or update the IFC model for <strong>{currentProject?.name}</strong> (Session A file lineage
        with SHA-256 digest).
      </p>

      <div
        class="rounded-2xl border-2 border-dashed border-slate-700 p-6 text-center transition-colors hover:border-slate-500"
      >
        <Upload class="mx-auto mb-2 h-8 w-8 text-slate-400" />
        <input
          type="file"
          accept=".ifc"
          onchange={(e) => (uploadFile = e.currentTarget.files?.[0] || null)}
          class="text-xs text-slate-300 file:mr-3 file:rounded-xl file:border-0 file:bg-accent file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-accent-hover"
        />
      </div>

      {#if uploadSuccessMsg}
        <div
          class="rounded-xl border border-emerald-800 bg-emerald-950/50 p-3 text-xs text-emerald-300"
        >
          {uploadSuccessMsg}
        </div>
      {/if}

      {#if uploadErrorMsg}
        <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
          {uploadErrorMsg}
        </div>
      {/if}

      <div class="flex items-center justify-end gap-2 pt-2">
        <button
          type="button"
          onclick={() => (isUploadModalOpen = false)}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={!uploadFile || isUploading}
          onclick={handleUploadIfc}
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {#if isUploading}
            <RefreshCw class="h-3.5 w-3.5 animate-spin" />
            <span>Uploading…</span>
          {:else}
            <span>Confirm Upload</span>
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
