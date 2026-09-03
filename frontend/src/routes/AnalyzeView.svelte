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
  import { isAbortError, analyzeApi, projectsApi, rulesApi } from "../lib/api";
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
  let searchQuery = $state("");
  let severityFilter = $state("all");
  let mechanismFilter = $state("all");

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
      const relevant = projects.filter((p) => {
        if (activeCategory === "seismic") {
          return (
            p.analysis_type === "seismic" ||
            p.analysis_type === "Seismic" ||
            p.analysis_type === "Halo"
          );
        }
        return p.analysis_type === "Piping" || p.analysis_type === "Piping (Corrosive)";
      });
      if (!selectedProjectId && relevant.length > 0) {
        selectedProjectId = relevant[0].id;
      }
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

  async function fetchResults(useCache = true) {
    if (!selectedProjectId) return;
    try {
      result = await analyzeApi.getResults(
        selectedProjectId,
        selectedSlug,
        useCache,
        requestedEngines,
      );
    } catch {
      // A miss here is the normal "no analysis has been run yet" case, not a
      // failure, so it stays quiet; handleRun surfaces real run errors.
      result = null;
    }
  }

  // Lets an in-flight run be abandoned, either by the user or because they
  // switched to a different project while it was still going.
  let runController: AbortController | null = null;

  async function handleRun(forceRecompute = false) {
    if (!selectedProjectId) return;
    runController?.abort();
    const controller = new AbortController();
    runController = controller;

    isRunning = true;
    error = "";
    // The previous report is deliberately kept until the new one lands: if this
    // run fails, discarding it first would have left the user with nothing but
    // an error message. It is dimmed while the run is in flight.
    try {
      const next = await analyzeApi.run(
        selectedProjectId,
        selectedSlug,
        false,
        !forceRecompute,
        requestedEngines,
        controller.signal,
      );
      if (runController !== controller) return; // superseded by a newer run
      result = next;
    } catch (err: any) {
      if (isAbortError(err)) return;
      error = err.message || "Analysis failed";
      toasts.fromError(err, "Analysis failed.");
    } finally {
      if (runController === controller) {
        runController = null;
        isRunning = false;
      }
    }
  }

  function handleCancelRun() {
    runController?.abort();
    runController = null;
    isRunning = false;
    toasts.info("Analysis cancelled.");
  }

  async function handleProjectChange() {
    runController?.abort();
    runController = null;
    isRunning = false;
    error = "";
    result = null;
    await Promise.all([fetchResults(), loadInputs()]);
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

  // Finding table multi-selection, sort, and pagination state
  let selectedFindingIds: string[] = $state([]);
  let findingSortField: "band" | "rule_id" | "element_id" | "title" | "score" = $state("band");
  let findingSortAsc = $state(false);
  let findingCurrentPage = $state(1);
  let findingPageSize = $state(10);

  const SEVERITY_WEIGHTS: Record<string, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
    data_quality: 0,
  };

  function toggleSelectAllFindings() {
    if (allFilteredFindingsSelected) {
      selectedFindingIds = [];
    } else {
      selectedFindingIds = sortedFilteredIssues.map((i) => i.id);
    }
  }

  function toggleSelectFinding(id: string) {
    if (selectedFindingIds.includes(id)) {
      selectedFindingIds = selectedFindingIds.filter((iId) => iId !== id);
    } else {
      selectedFindingIds = [...selectedFindingIds, id];
    }
  }

  function toggleFindingSort(field: "band" | "rule_id" | "element_id" | "title" | "score") {
    if (findingSortField === field) {
      findingSortAsc = !findingSortAsc;
    } else {
      findingSortField = field;
      findingSortAsc = true;
    }
  }

  function exportFindingsToCsv() {
    const toExport = (result?.audit_issues || []).filter((i) => selectedFindingIds.includes(i.id));
    const target = toExport.length ? toExport : sortedFilteredIssues;
    const headers = [
      "FindingID",
      "Severity",
      "Mechanism",
      "RuleID",
      "ElementGUID",
      "Title",
      "Description",
      "Score",
      "IntrusionDepthMM",
      "Mitigation",
    ];
    const rows = target.map((i) => [
      `"${(i.id || "").replace(/"/g, '""')}"`,
      `"${(i.band || "").replace(/"/g, '""')}"`,
      `"${(i.mechanism || "").replace(/"/g, '""')}"`,
      `"${(i.rule_id || "").replace(/"/g, '""')}"`,
      `"${(i.element_id || "").replace(/"/g, '""')}"`,
      `"${(i.title || "").replace(/"/g, '""')}"`,
      `"${(i.description || "").replace(/"/g, '""')}"`,
      i.score ?? "",
      i.details?.intrusion_depth_mm ?? "",
      `"${(i.mitigation || "").replace(/"/g, '""')}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `compliance_findings_${currentProject?.name || "project"}_${new Date().toISOString().substring(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
  let relevantProjects = $derived(
    projects.filter((p) => {
      if (activeCategory === "seismic") {
        return (
          p.analysis_type === "seismic" ||
          p.analysis_type === "Seismic" ||
          p.analysis_type === "Halo"
        );
      }
      return p.analysis_type === "Piping" || p.analysis_type === "Piping (Corrosive)";
    }),
  );
  let currentRelevantKey = $derived(
    `${activeCategory}_${relevantProjects.map((p) => p.id).join(",")}`,
  );
  run(() => {
    if (relevantProjects.length > 0 && currentRelevantKey !== prevRelevantKey) {
      prevRelevantKey = currentRelevantKey;
      if (!selectedProjectId || !relevantProjects.some((p) => p.id === selectedProjectId)) {
        selectedProjectId = relevantProjects[0].id;
        handleProjectChange();
      }
    }
  });
  let currentProject = $derived(relevantProjects.find((p) => p.id === selectedProjectId) || null);
  let filteredIssues = $derived(
    (result?.audit_issues || []).filter((issue: AuditIssue) => {
      // Low risk filter (Note: data_quality issues are doctrine-exempt and ALWAYS shown)
      if (
        !showLowRisk &&
        issue.band === "low" &&
        issue.mechanism !== "data_quality" &&
        issue.mechanism !== "Data Quality"
      ) {
        return false;
      }

      const matchesSearch =
        searchQuery === "" ||
        issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        issue.rule_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        issue.element_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        issue.mechanism.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (issue.citations || []).some(
          (c) =>
            c.standard.toLowerCase().includes(searchQuery.toLowerCase()) ||
            c.clause.toLowerCase().includes(searchQuery.toLowerCase()),
        );

      const matchesSeverity =
        severityFilter === "all" ||
        (severityFilter === "data_quality"
          ? issue.mechanism === "data_quality" || issue.mechanism === "Data Quality"
          : issue.band === severityFilter &&
            issue.mechanism !== "data_quality" &&
            issue.mechanism !== "Data Quality");

      const matchesMechanism =
        mechanismFilter === "all" ||
        (mechanismFilter === "data_quality"
          ? issue.mechanism === "data_quality" || issue.mechanism === "Data Quality"
          : issue.rule_id.startsWith(mechanismFilter) || issue.mechanism.includes(mechanismFilter));

      // Engine selector, PIPING only. Data-quality findings are doctrine-exempt:
      // they report what could not be assessed and belong to no single engine.
      const isDataQuality =
        issue.mechanism === "data_quality" || issue.mechanism === "Data Quality";
      const matchesEngine =
        activeCategory === "seismic" ||
        isDataQuality ||
        selectedEngines.some((id) => issue.rule_id.startsWith(id) || issue.mechanism.includes(id));

      return matchesSearch && matchesSeverity && matchesMechanism && matchesEngine;
    }),
  );
  // Data-quality findings are doctrine-exempt: they report what could not be
  // assessed rather than a violation, so they are counted separately from the
  // severity bands. Older payloads may omit the stat, hence the fallback.
  let dataQualityCount = $derived(
    result?.issue_stats?.data_quality ??
      (result?.audit_issues || []).filter(
        (issue: AuditIssue) =>
          issue.mechanism === "data_quality" || issue.mechanism === "Data Quality",
      ).length,
  );
  let sortedFilteredIssues = $derived(
    [...filteredIssues].sort((a, b) => {
      let valA: any = a[findingSortField];
      let valB: any = b[findingSortField];
      if (findingSortField === "band") {
        valA = SEVERITY_WEIGHTS[(a.band || "").toLowerCase()] ?? 0;
        valB = SEVERITY_WEIGHTS[(b.band || "").toLowerCase()] ?? 0;
      } else {
        if (valA === undefined || valA === null) valA = "";
        if (valB === undefined || valB === null) valB = "";
        if (typeof valA === "string") valA = valA.toLowerCase();
        if (typeof valB === "string") valB = valB.toLowerCase();
      }
      if (valA < valB) return findingSortAsc ? -1 : 1;
      if (valA > valB) return findingSortAsc ? 1 : -1;
      return 0;
    }),
  );
  let findingTotalItems = $derived(sortedFilteredIssues.length);
  let paginatedIssues = $derived(
    sortedFilteredIssues.slice(
      (findingCurrentPage - 1) * findingPageSize,
      findingCurrentPage * findingPageSize,
    ),
  );
  let allFilteredFindingsSelected = $derived(
    sortedFilteredIssues.length > 0 &&
      sortedFilteredIssues.every((i) => selectedFindingIds.includes(i.id)),
  );
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
          class="inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-xs font-semibold {activeCategory ===
          'seismic'
            ? 'border-purple-800/80 bg-purple-950/60 text-purple-300 shadow-sm'
            : 'border-amber-800/80 bg-amber-950/60 text-amber-300 shadow-sm'}"
        >
          Category: {activeCategory}
        </span>
        {#if result?.cached}
          <span
            class="inline-flex items-center gap-1 rounded-full border border-blue-800/80 bg-blue-950/80 px-2.5 py-0.5 text-caption font-semibold text-blue-300 shadow-sm"
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
          {#each categoryFolders as folder}
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

    <!-- Actions & Project Selector -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- Project Dropdown -->
      <div class="relative">
        <select
          bind:value={selectedProjectId}
          onchange={handleProjectChange}
          class="cursor-pointer appearance-none rounded-2xl border border-slate-800 bg-slate-900 px-4 py-2 pr-8 text-xs font-medium text-slate-50 shadow-sm focus:border-accent focus:outline-none"
        >
          {#if relevantProjects.length === 0}
            <option value={null}>No {activeCategory} projects found</option>
          {:else}
            {#each relevantProjects as p}
              <option value={p.id}>{p.name} ({p.country})</option>
            {/each}
          {/if}
        </select>
        <ChevronRight
          class="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 rotate-90 text-slate-400"
        />
      </div>

      <!-- Run Action Button -->
      <button
        type="button"
        disabled={isRunning || !currentProject?.ifc_file_path || engineSelectionEmpty}
        title={engineSelectionEmpty
          ? "Select at least one engine to run"
          : "Run the audit against the selected engines"}
        onclick={() => handleRun(false)}
        class="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-blue-500/25 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:pointer-events-none disabled:opacity-50"
      >
        {#if isRunning}
          <RefreshCw class="h-3.5 w-3.5 animate-spin" />
          <span>Running Engine…</span>
        {:else}
          <Play class="h-3.5 w-3.5 fill-current" />
          <span>Run Audit</span>
        {/if}
      </button>

      {#if isRunning}
        <button
          type="button"
          onclick={handleCancelRun}
          class="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
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
          {#each PIPING_ENGINES as engine}
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
                  class="inline-flex cursor-pointer select-none items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-caption font-semibold transition-colors {selectedEngines.includes(
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
          class="rounded-full border border-slate-800 bg-slate-900/80 p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
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
            {#each analysisInputs as inp}
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
              <span class="rounded-full bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                {filteredIssues.length} of {result.audit_issues.length}
              </span>
            </h2>
            <p class="mt-0.5 text-xs text-slate-400">
              Component compliance verdicts, authoritative citations, and actionable engineering
              mitigations.
            </p>
          </div>

          <!-- Multi-Format Export Actions (Session E) -->
          <div class="flex items-center gap-2">
            {#if selectedProjectId}
              <a
                href={analyzeApi.getExportUrl(
                  selectedProjectId,
                  selectedSlug,
                  "bcf",
                  requestedEngines,
                )}
                class="inline-flex items-center gap-1.5 rounded-full bg-accent px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:scale-[1.02] hover:bg-accent-hover"
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
                )}
                class="inline-flex items-center gap-1.5 rounded-full bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
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
                )}
                class="inline-flex items-center gap-1.5 rounded-full bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
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
              bind:value={searchQuery}
              placeholder="Search findings by rule, GUID, title, or citation (e.g. NASA-STD, EN 1998)…"
              class="w-full rounded-xl border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>

          <!-- Severity Filter -->
          <div class="sm:col-span-3">
            <select
              bind:value={severityFilter}
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
              bind:value={mechanismFilter}
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
              bind:checked={showLowRisk}
              class="h-3.5 w-3.5 rounded border-slate-700 bg-slate-900 text-accent focus:ring-0"
            />
            <span>Include Low Severity verdicts in list</span>
          </label>
          <span class="text-caption text-slate-500">
            Showing {filteredIssues.length} items
          </span>
        </div>

        <!-- Bulk Actions Bar -->
        <BulkActionBar
          selectedCount={selectedFindingIds.length}
          itemLabel="finding"
          onClearSelection={() => (selectedFindingIds = [])}
          onBulkExport={exportFindingsToCsv}
          onBulkDelete={null}
          onBulkEdit={null}
        />

        <!-- Tabular Findings Table -->
        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/50">
          {#if sortedFilteredIssues.length === 0}
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
                        checked={allFilteredFindingsSelected}
                        onchange={toggleSelectAllFindings}
                        class="h-4 w-4 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent focus:ring-accent"
                        title="Select all findings"
                      />
                    </th>
                    <th
                      class="cursor-pointer select-none px-4 py-3.5 transition-colors hover:text-slate-50"
                      onclick={() => toggleFindingSort("band")}
                    >
                      <div class="flex items-center gap-1">
                        <span>Severity</span>
                        {#if findingSortField === "band"}
                          {#if findingSortAsc}<ArrowUp
                              class="h-3 w-3 text-accent"
                            />{:else}<ArrowDown class="h-3 w-3 text-accent" />{/if}
                        {:else}
                          <ArrowUpDown class="h-3 w-3 text-slate-600" />
                        {/if}
                      </div>
                    </th>
                    <th
                      class="cursor-pointer select-none px-4 py-3.5 transition-colors hover:text-slate-50"
                      onclick={() => toggleFindingSort("rule_id")}
                    >
                      <div class="flex items-center gap-1">
                        <span>Rule &amp; Mechanism</span>
                        {#if findingSortField === "rule_id"}
                          {#if findingSortAsc}<ArrowUp
                              class="h-3 w-3 text-accent"
                            />{:else}<ArrowDown class="h-3 w-3 text-accent" />{/if}
                        {:else}
                          <ArrowUpDown class="h-3 w-3 text-slate-600" />
                        {/if}
                      </div>
                    </th>
                    <th
                      class="cursor-pointer select-none px-4 py-3.5 transition-colors hover:text-slate-50"
                      onclick={() => toggleFindingSort("element_id")}
                    >
                      <div class="flex items-center gap-1">
                        <span>Element GUID</span>
                        {#if findingSortField === "element_id"}
                          {#if findingSortAsc}<ArrowUp
                              class="h-3 w-3 text-accent"
                            />{:else}<ArrowDown class="h-3 w-3 text-accent" />{/if}
                        {:else}
                          <ArrowUpDown class="h-3 w-3 text-slate-600" />
                        {/if}
                      </div>
                    </th>
                    <th
                      class="cursor-pointer select-none px-4 py-3.5 transition-colors hover:text-slate-50"
                      onclick={() => toggleFindingSort("title")}
                    >
                      <div class="flex items-center gap-1">
                        <span>Finding &amp; Citations</span>
                        {#if findingSortField === "title"}
                          {#if findingSortAsc}<ArrowUp
                              class="h-3 w-3 text-accent"
                            />{:else}<ArrowDown class="h-3 w-3 text-accent" />{/if}
                        {:else}
                          <ArrowUpDown class="h-3 w-3 text-slate-600" />
                        {/if}
                      </div>
                    </th>
                    <th
                      class="cursor-pointer select-none px-4 py-3.5 text-center transition-colors hover:text-slate-50"
                      onclick={() => toggleFindingSort("score")}
                    >
                      <div class="flex items-center justify-center gap-1">
                        <span>Score / Clearance</span>
                        {#if findingSortField === "score"}
                          {#if findingSortAsc}<ArrowUp
                              class="h-3 w-3 text-accent"
                            />{:else}<ArrowDown class="h-3 w-3 text-accent" />{/if}
                        {:else}
                          <ArrowUpDown class="h-3 w-3 text-slate-600" />
                        {/if}
                      </div>
                    </th>
                    <th class="px-4 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60">
                  {#each paginatedIssues as issue}
                    {@const isDq =
                      issue.mechanism === "data_quality" || issue.mechanism === "Data Quality"}
                    <tr
                      class="group transition-colors hover:bg-slate-900/60 {selectedFindingIds.includes(
                        issue.id,
                      )
                        ? 'bg-blue-950/20'
                        : ''}"
                    >
                      <!-- Row Checkbox -->
                      <td class="w-10 px-4 py-3.5 align-top">
                        <input
                          type="checkbox"
                          checked={selectedFindingIds.includes(issue.id)}
                          onchange={() => toggleSelectFinding(issue.id)}
                          class="h-4 w-4 cursor-pointer rounded border-slate-700 bg-slate-950 text-accent focus:ring-accent"
                        />
                      </td>

                      <!-- Severity Band Pill -->
                      <td class="whitespace-nowrap px-4 py-3.5 align-top">
                        {#if isDq}
                          <span
                            class="inline-block rounded-full border border-slate-700 bg-slate-800 px-2.5 py-0.5 text-micro font-semibold uppercase text-slate-300"
                          >
                            Data Quality
                          </span>
                        {:else if issue.band === "critical"}
                          <span
                            class="inline-block rounded-full border border-red-800/80 bg-red-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-red-400 shadow-sm"
                          >
                            Critical
                          </span>
                        {:else if issue.band === "high"}
                          <span
                            class="inline-block rounded-full border border-orange-800/80 bg-orange-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-orange-400 shadow-sm"
                          >
                            High
                          </span>
                        {:else if issue.band === "medium"}
                          <span
                            class="inline-block rounded-full border border-yellow-800/80 bg-yellow-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-yellow-400 shadow-sm"
                          >
                            Medium
                          </span>
                        {:else}
                          <span
                            class="inline-block rounded-full border border-emerald-800/80 bg-emerald-950/80 px-2.5 py-0.5 text-micro font-semibold uppercase text-emerald-400 shadow-sm"
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
                            {#each issue.citations as cit}
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
              currentPage={findingCurrentPage}
              pageSize={findingPageSize}
              totalItems={findingTotalItems}
              onPageChange={(p) => (findingCurrentPage = p)}
              onPageSizeChange={(s) => {
                findingPageSize = s;
                findingCurrentPage = 1;
              }}
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
  {@const isDq =
    inspectedIssue.mechanism === "data_quality" || inspectedIssue.mechanism === "Data Quality"}
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
            {#each inspectedIssue.citations as cit}
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
