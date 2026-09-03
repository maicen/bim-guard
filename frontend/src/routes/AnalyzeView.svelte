<script lang="ts">
  import { onMount } from "svelte";
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
  import { analyzeApi, projectsApi, rulesApi } from "../lib/api";
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

  export let initialProjectId: number | null = null;
  export let activeCategory: "Piping" | "seismic" = "Piping";
  export let onSelectProjectForViewer: (
    projectId: number,
    elementGuid?: string,
    bcfArtifactId?: number,
  ) => void;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let selectedSlug: "corrosion" | "seismic" = "corrosion";
  $: selectedSlug = activeCategory === "seismic" ? "seismic" : "corrosion";
  let isRunning = false;
  let error = "";
  let result: AnalysisResult | null = null;
  let analysisInputs: AnalysisInputItem[] = [];

  let categoryFolders: RuleFolder[] = [];
  let isFoldersLoading = false;

  async function loadCategoryFolders(cat: "Piping" | "seismic") {
    isFoldersLoading = true;
    try {
      categoryFolders = await rulesApi.folders(cat);
    } catch (err) {
      categoryFolders = [];
      toasts.fromError(err, 'Could not load rule folders for this category.');
    } finally {
      isFoldersLoading = false;
    }
  }

  $: {
    loadCategoryFolders(activeCategory);
  }

  // Options & Filters
  let searchQuery = "";
  let severityFilter = "all";
  let mechanismFilter = "all";

  // Engine selector (PIPING only). SEISMIC runs the single Blue Halo kernel,
  // so a selector there would offer a choice of one.
  const PIPING_ENGINES = [
    { id: "GC", label: "GC-001", title: "Galvanic corrosion" },
    { id: "CC", label: "CC-001", title: "Crevice corrosion" },
    { id: "MC", label: "MC-001", title: "Microbiologically influenced corrosion" },
    { id: "MM", label: "MM-001", title: "Material-media compatibility" },
    { id: "XM", label: "XM-001", title: "Cross-material compatibility" },
  ] as const;
  let selectedEngines: string[] = PIPING_ENGINES.map((e) => e.id);

  // Leaving the category resets the selector, so a narrowed PIPING view never
  // silently hides findings after a route change.
  $: if (activeCategory) selectedEngines = PIPING_ENGINES.map((e) => e.id);

  // What the backend is asked to run. SEISMIC is a single kernel with nothing
  // to select between, so it sends no selection at all.
  $: requestedEngines =
    activeCategory === "seismic" ? undefined : selectedEngines;

  // A run with no engine selected assesses nothing, so the button is disabled
  // rather than returning an empty audit that looks like a clean model.
  $: engineSelectionEmpty =
    activeCategory !== "seismic" && selectedEngines.length === 0;

  function toggleEngine(id: string) {
    selectedEngines = selectedEngines.includes(id)
      ? selectedEngines.filter((e) => e !== id)
      : [...selectedEngines, id];
  }
  let showLowRisk = true;
  let isUploadModalOpen = false;
  let uploadFile: File | null = null;
  let isUploading = false;
  let uploadSuccessMsg = "";
  let uploadErrorMsg = "";
  let copiedGuid = "";

  // Inspection Drawer/Modal state
  let inspectedIssue: AuditIssue | null = null;

  $: relevantProjects = projects.filter((p) => {
    if (activeCategory === "seismic") {
      return (
        p.analysis_type === "seismic" ||
        p.analysis_type === "Seismic" ||
        p.analysis_type === "Halo"
      );
    }
    return (
      p.analysis_type === "Piping" ||
      p.analysis_type === "Piping (Corrosive)"
    );
  });
  $: currentProject = relevantProjects.find((p) => p.id === selectedProjectId) || null;

  let prevRelevantKey = "";
  $: currentRelevantKey = `${activeCategory}_${relevantProjects.map((p) => p.id).join(",")}`;
  $: if (relevantProjects.length > 0 && currentRelevantKey !== prevRelevantKey) {
    prevRelevantKey = currentRelevantKey;
    if (!selectedProjectId || !relevantProjects.some((p) => p.id === selectedProjectId)) {
      selectedProjectId = relevantProjects[0].id;
      handleProjectChange();
    }
  }

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
        return (
          p.analysis_type === "Piping" ||
          p.analysis_type === "Piping (Corrosive)"
        );
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
      toasts.fromError(err, 'Could not load the analysis inputs for this project.');
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

  async function handleRun(forceRecompute = false) {
    if (!selectedProjectId) return;
    isRunning = true;
    error = "";
    result = null;
    try {
      result = await analyzeApi.run(
        selectedProjectId,
        selectedSlug,
        false,
        !forceRecompute,
        requestedEngines,
      );
    } catch (err: any) {
      error = err.message || "Analysis failed";
    } finally {
      isRunning = false;
    }
  }

  async function handleProjectChange() {
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
      setTimeout(() => {
        isUploadModalOpen = false;
        uploadSuccessMsg = "";
      }, 1500);
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

  $: filteredIssues = (result?.audit_issues || []).filter(
    (issue: AuditIssue) => {
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
          ? issue.mechanism === "data_quality" ||
            issue.mechanism === "Data Quality"
          : issue.band === severityFilter &&
            issue.mechanism !== "data_quality" &&
            issue.mechanism !== "Data Quality");

      const matchesMechanism =
        mechanismFilter === "all" ||
        (mechanismFilter === "data_quality"
          ? issue.mechanism === "data_quality" ||
            issue.mechanism === "Data Quality"
          : issue.rule_id.startsWith(mechanismFilter) ||
            issue.mechanism.includes(mechanismFilter));

      // Engine selector, PIPING only. Data-quality findings are doctrine-exempt:
      // they report what could not be assessed and belong to no single engine.
      const isDataQuality =
        issue.mechanism === "data_quality" || issue.mechanism === "Data Quality";
      const matchesEngine =
        activeCategory === "seismic" ||
        isDataQuality ||
        selectedEngines.some(
          (id) =>
            issue.rule_id.startsWith(id) || issue.mechanism.includes(id),
        );

      return (
        matchesSearch && matchesSeverity && matchesMechanism && matchesEngine
      );
    },
  );

  // Data-quality findings are doctrine-exempt: they report what could not be
  // assessed rather than a violation, so they are counted separately from the
  // severity bands. Older payloads may omit the stat, hence the fallback.
  $: dataQualityCount =
    result?.issue_stats?.data_quality ??
    (result?.audit_issues || []).filter(
      (issue: AuditIssue) =>
        issue.mechanism === "data_quality" || issue.mechanism === "Data Quality",
    ).length;

  // Finding table multi-selection, sort, and pagination state
  let selectedFindingIds: string[] = [];
  let findingSortField: "band" | "rule_id" | "element_id" | "title" | "score" = "band";
  let findingSortAsc = false;
  let findingCurrentPage = 1;
  let findingPageSize = 10;

  const SEVERITY_WEIGHTS: Record<string, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
    data_quality: 0,
  };

  $: sortedFilteredIssues = [...filteredIssues].sort((a, b) => {
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
  });

  $: findingTotalItems = sortedFilteredIssues.length;
  $: paginatedIssues = sortedFilteredIssues.slice(
    (findingCurrentPage - 1) * findingPageSize,
    findingCurrentPage * findingPageSize,
  );

  $: allFilteredFindingsSelected =
    sortedFilteredIssues.length > 0 &&
    sortedFilteredIssues.every((i) => selectedFindingIds.includes(i.id));

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
    const headers = ["FindingID", "Severity", "Mechanism", "RuleID", "ElementGUID", "Title", "Description", "Score", "IntrusionDepthMM", "Mitigation"];
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
    link.setAttribute("download", `compliance_findings_${currentProject?.name || "project"}_${new Date().toISOString().substring(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
</script>

<div class="space-y-6 pb-12">
  <!-- Top Navigation & Title Bar -->
  <div
    class="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800/80 pb-6"
  >
    <div>
      <div
        class="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-accent mb-1"
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
        class="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50 flex items-center gap-3 flex-wrap"
      >
        <span
          >{activeCategory === "seismic"
            ? "Seismic Buffer & Bracing Audit"
            : "Piping System Corrosion Audit"}</span
        >
        <span
          class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono border {activeCategory ===
          'seismic'
            ? 'bg-purple-950/60 text-purple-300 border-purple-800/80 shadow-sm'
            : 'bg-amber-950/60 text-amber-300 border-amber-800/80 shadow-sm'}"
        >
          Category: {activeCategory}
        </span>
        {#if result?.cached}
          <span
            class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-caption font-semibold bg-blue-950/80 text-blue-300 border border-blue-800/80 shadow-sm"
          >
            <Sparkles class="w-3 h-3 text-blue-400" />
            Cached SHA-256
          </span>
        {/if}
      </h1>
      <p class="text-xs sm:text-sm text-slate-400 mt-1 max-w-3xl">
        {#if activeCategory === "seismic"}
          Execute verified Blue Halo Seismic Clearance (SB-001 / EN 1998-1 / DIN
          4149) buffer volume and bracing audits.
        {:else}
          Execute verified Galvanic (GC-001), Crevice (CC-001),
          Microbiological (MC-001), Material-media (MM-001), and
          Cross-material (XM-001) piping compliance audits.
        {/if}
      </p>

      <!-- Active Rulesets within this category -->
      {#if categoryFolders.length > 0}
        <div class="flex items-center gap-1.5 flex-wrap mt-3">
          <span
            class="text-micro font-bold uppercase tracking-wider text-slate-500"
            >Active Rulesets:</span
          >
          {#each categoryFolders as folder}
            <span
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-micro font-mono font-medium border {activeCategory ===
              'seismic'
                ? 'bg-purple-950/40 border-purple-800/50 text-purple-300'
                : 'bg-amber-950/40 border-amber-800/50 text-amber-300'}"
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
          on:change={handleProjectChange}
          class="bg-slate-900 border border-slate-800 rounded-2xl px-4 py-2 text-xs font-medium text-slate-50 focus:outline-none focus:border-accent shadow-sm appearance-none pr-8 cursor-pointer"
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
          class="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 rotate-90 pointer-events-none"
        />
      </div>

      <!-- Run Action Button -->
      <button
        type="button"
        disabled={isRunning ||
          !currentProject?.ifc_file_path ||
          engineSelectionEmpty}
        title={engineSelectionEmpty
          ? "Select at least one engine to run"
          : "Run the audit against the selected engines"}
        on:click={() => handleRun(false)}
        class="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold bg-accent hover:bg-accent-hover text-white shadow-lg shadow-blue-500/25 transition-all hover:scale-[1.02] disabled:opacity-50 disabled:pointer-events-none"
      >
        {#if isRunning}
          <RefreshCw class="w-3.5 h-3.5 animate-spin" />
          <span>Running Engine…</span>
        {:else}
          <Play class="w-3.5 h-3.5 fill-current" />
          <span>Run Audit</span>
        {/if}
      </button>

      <!-- Engine Selector (PIPING only) -->
      {#if activeCategory !== "seismic"}
        <div
          class="flex items-center gap-2 pl-1 border-l border-slate-800"
          role="group"
          aria-label="Corrosion engines"
        >
          <span
            class="text-micro font-bold uppercase tracking-wider text-slate-500"
            >Engines</span
          >
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
              <label
                slot="trigger"
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-caption font-mono font-semibold border cursor-pointer select-none transition-colors {selectedEngines.includes(
                  engine.id,
                )
                  ? 'bg-amber-950/60 text-amber-300 border-amber-800/80'
                  : 'bg-slate-900/60 text-slate-500 border-slate-800 hover:text-slate-300'}"
              >
                <input
                  type="checkbox"
                  class="sr-only"
                  checked={selectedEngines.includes(engine.id)}
                  on:change={() => toggleEngine(engine.id)}
                />
                {#if selectedEngines.includes(engine.id)}
                  <Check class="w-3 h-3" />
                {/if}
                <span>{engine.label}</span>
              </label>

              {info?.description || engine.title}

              <span slot="footer" class="font-mono">{info?.reference}</span>
            </HoverCard>
          {/each}
        </div>
      {/if}

      <!-- Recompute (force uncached) -->
      {#if result}
        <button
          type="button"
          disabled={isRunning ||
            !currentProject?.ifc_file_path ||
            engineSelectionEmpty}
          on:click={() => handleRun(true)}
          title="Force uncached recomputation against the latest IFC digest"
          class="p-2 rounded-full border border-slate-800 bg-slate-900/80 hover:bg-slate-800 text-slate-400 hover:text-slate-50 transition-colors"
        >
          <RefreshCw class="w-3.5 h-3.5 {isRunning ? 'animate-spin' : ''}" />
        </button>
      {/if}
    </div>
  </div>

  <!-- Project Readiness & Lineage Section (Session A / B) -->
  {#if currentProject}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- Project Metadata Card -->
      <div
        class="p-4 rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-3"
      >
        <div class="flex items-center justify-between">
          <span
            class="text-xs uppercase font-bold tracking-wider text-slate-400"
            >Target Project</span
          >
          <span
            class="px-2 py-0.5 rounded text-micro font-semibold uppercase {currentProject.status ===
            'Active'
              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60'
              : 'bg-slate-800 text-slate-400'}"
          >
            {currentProject.status}
          </span>
        </div>
        <div>
          <div class="text-sm font-bold text-slate-50 truncate">
            {currentProject.name}
          </div>
          <div class="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
            <span>Jurisdiction: <strong>{currentProject.country}</strong></span>
            <span>•</span>
            <span>Type: <strong>{currentProject.analysis_type}</strong></span>
          </div>
        </div>
      </div>

      <!-- IFC Model Card & Lineage -->
      <div
        class="p-4 rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-3"
      >
        <div class="flex items-center justify-between">
          <span
            class="text-xs uppercase font-bold tracking-wider text-slate-400"
            >IFC Model Lineage</span
          >
          {#if currentProject.ifc_file_path}
            <span
              class="px-2 py-0.5 rounded text-micro font-semibold uppercase bg-emerald-950/60 text-emerald-400 border border-emerald-800/60"
            >
              Model Ready
            </span>
          {:else}
            <span
              class="px-2 py-0.5 rounded text-micro font-semibold uppercase bg-amber-950/60 text-amber-400 border border-amber-800/60"
            >
              No Model Attached
            </span>
          {/if}
        </div>
        {#if currentProject.ifc_file_path}
          <div class="text-xs space-y-1">
            <div
              class="text-slate-300 font-mono text-caption truncate"
              title={currentProject.ifc_file_path}
            >
              {currentProject.ifc_file_path.split("/").pop()}
            </div>
            {#if currentProject.ifc_md5_hash}
              <div
                class="text-slate-500 font-mono text-micro flex items-center gap-1.5"
              >
                <span>Digest: {currentProject.ifc_md5_hash.slice(0, 16)}…</span>
                <button
                  type="button"
                  on:click={() => copyText(currentProject?.ifc_md5_hash || "")}
                  class="hover:text-slate-300"
                >
                  <Copy class="w-3 h-3" />
                </button>
              </div>
            {/if}
          </div>
          <div class="flex items-center gap-2 pt-1">
            <button
              type="button"
              on:click={() => onSelectProjectForViewer(currentProject.id)}
              class="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:text-blue-400 transition-colors"
            >
              <ScanEye class="w-3.5 h-3.5" />
              <span>Open 3D Viewer</span>
            </button>
            <span class="text-slate-700">•</span>
            <button
              type="button"
              on:click={() => (isUploadModalOpen = true)}
              class="text-xs text-slate-400 hover:text-slate-50 transition-colors"
            >
              Replace Model
            </button>
          </div>
        {:else}
          <div class="text-xs text-amber-300/80">
            Attach an IFC model to run compliance checks.
          </div>
          <button
            type="button"
            on:click={() => (isUploadModalOpen = true)}
            class="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-400 hover:text-amber-300"
          >
            <Upload class="w-3.5 h-3.5" />
            <span>Upload IFC Model</span>
          </button>
        {/if}
      </div>

      <!-- Analysis Inputs (Standards & Client Docs) -->
      <div
        class="p-4 rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-3"
      >
        <div class="flex items-center justify-between">
          <span
            class="text-xs uppercase font-bold tracking-wider text-slate-400"
            >Linked Standards &amp; Inputs</span
          >
          <span class="text-xs font-mono font-bold text-slate-300"
            >{analysisInputs.length} linked</span
          >
        </div>
        {#if analysisInputs.length > 0}
          <div class="flex flex-wrap gap-1.5 max-h-16 overflow-y-auto pr-1">
            {#each analysisInputs as inp}
              <span
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-micro font-medium {inp.kind ===
                'standard'
                  ? 'bg-indigo-950/60 text-indigo-300 border border-indigo-800/60'
                  : 'bg-teal-950/60 text-teal-300 border border-teal-800/60'}"
              >
                {inp.label}
              </span>
            {/each}
          </div>
        {:else}
          <div class="text-xs text-slate-500">
            Default regulatory rulepacks will be evaluated.
          </div>
        {/if}
        <div class="pt-1 flex items-center gap-1.5 text-micro text-slate-400 border-t border-slate-800/60">
          <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-950/60 text-blue-300 border border-blue-800/60 font-semibold">
            <ShieldCheck class="w-3 h-3 text-blue-400" />
            bSDD Verified
          </span>
          <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/60 font-semibold">
            <CheckCircle2 class="w-3 h-3 text-amber-400" />
            IDS 1.0 Compliant
          </span>
        </div>
      </div>
    </div>
  {/if}

  <!-- Error Alerts -->
  {#if error}
    <div
      class="p-4 rounded-2xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-3"
    >
      <ShieldAlert class="w-5 h-5 text-rose-400 shrink-0" />
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

  <!-- Results Section -->
  {#if result}
    <!-- Demo Mode Notice -->
    {#if result.compliance_is_demo}
      <div
        class="p-4 rounded-2xl bg-amber-950/40 border border-amber-800/70 text-amber-300 text-xs flex items-center gap-2.5"
      >
        <AlertTriangle class="w-4 h-4 text-amber-400 shrink-0" />
        <span
          ><strong>Demo Compliance Mode:</strong> Results are generated from demonstration
          test cases.</span
        >
      </div>
    {/if}

    <!-- Data Quality Doctrine Notice -->
    {#if dataQualityCount > 0}
      <div
        class="p-4 rounded-2xl bg-blue-950/40 border border-blue-800/70 text-blue-200 text-xs flex items-start gap-3 shadow-sm"
      >
        <Info class="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
        <div>
          <strong class="font-bold text-slate-50"
            >White Box Data-Quality Doctrine:</strong
          >
          <span>
            {dataQualityCount} unassessed service elements are explicitly reported
            below as <strong>Data Quality</strong> findings (assigned to the BIM
            Coordinator) rather than fabricating a false compliance pass.
          </span>
        </div>
      </div>
    {/if}

    <!-- Executive KPI Statistics Grid -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <div
        class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-sm"
      >
        <div
          class="text-caption text-slate-400 font-semibold uppercase tracking-wider"
        >
          Total Findings
        </div>
        <div class="text-2xl font-bold text-slate-50 mt-1">
          {result.issue_stats.total}
        </div>
        <div class="text-micro text-slate-500 mt-0.5">Non-compliant items</div>
      </div>
      <div
        class="p-4 rounded-2xl bg-red-950/30 border border-red-900/40 shadow-sm"
      >
        <div
          class="text-caption text-red-300 font-semibold uppercase tracking-wider"
        >
          Critical
        </div>
        <div class="text-2xl font-bold text-red-400 mt-1">
          {result.issue_stats.critical}
        </div>
        <div class="text-micro text-red-400/60 mt-0.5">
          Immediate intervention
        </div>
      </div>
      <div
        class="p-4 rounded-2xl bg-orange-950/30 border border-orange-900/40 shadow-sm"
      >
        <div
          class="text-caption text-orange-300 font-semibold uppercase tracking-wider"
        >
          High Risk
        </div>
        <div class="text-2xl font-bold text-orange-400 mt-1">
          {result.issue_stats.high}
        </div>
        <div class="text-micro text-orange-400/60 mt-0.5">
          Mandatory remediation
        </div>
      </div>
      <div
        class="p-4 rounded-2xl bg-yellow-950/30 border border-yellow-900/40 shadow-sm"
      >
        <div
          class="text-caption text-yellow-300 font-semibold uppercase tracking-wider"
        >
          Medium Risk
        </div>
        <div class="text-2xl font-bold text-yellow-400 mt-1">
          {result.issue_stats.medium}
        </div>
        <div class="text-micro text-yellow-400/60 mt-0.5">
          Recommended mitigation
        </div>
      </div>
      <div
        class="p-4 rounded-2xl bg-emerald-950/30 border border-emerald-900/40 shadow-sm"
      >
        <div
          class="text-caption text-emerald-300 font-semibold uppercase tracking-wider"
        >
          Low Risk
        </div>
        <div class="text-2xl font-bold text-emerald-400 mt-1">
          {result.issue_stats.low}
        </div>
        <div class="text-micro text-emerald-400/60 mt-0.5">
          Minor tolerance variance
        </div>
      </div>
      <div
        class="p-4 rounded-2xl bg-indigo-950/30 border border-indigo-900/40 shadow-sm"
      >
        <div
          class="text-caption text-indigo-300 font-semibold uppercase tracking-wider"
        >
          Data Quality
        </div>
        <div class="text-2xl font-bold text-indigo-300 mt-1">
          {dataQualityCount}
        </div>
        <div class="text-micro text-indigo-300/60 mt-0.5">
          Unassessed mechanisms
        </div>
      </div>
    </div>

    <!-- Findings Table & Export Controls -->
    <div
      class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-5"
    >
      <!-- Toolbar Header -->
      <div
        class="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
      >
        <div>
          <h2
            class="text-base font-bold text-slate-50 tracking-tight flex items-center gap-2"
          >
            <span>Audit Findings</span>
            <span
              class="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono"
            >
              {filteredIssues.length} of {result.audit_issues.length}
            </span>
          </h2>
          <p class="text-xs text-slate-400 mt-0.5">
            Component compliance verdicts, authoritative citations, and
            actionable engineering mitigations.
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
              class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-accent hover:bg-accent-hover text-white shadow-sm transition-all hover:scale-[1.02]"
              title="Download standard OpenBIM BCF 2.1 archive for Revit, Solibri, and Navisworks"
            >
              <Download class="w-3.5 h-3.5" />
              <span>Export BCF 2.1</span>
            </a>
            <a
              href={analyzeApi.getExportUrl(
                selectedProjectId,
                selectedSlug,
                "csv",
                requestedEngines,
              )}
              class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-50 transition-colors"
              title="Download tabulated audit spreadsheet with lineage and citations"
            >
              <Download class="w-3.5 h-3.5" />
              <span>CSV</span>
            </a>
            <a
              href={analyzeApi.getExportUrl(
                selectedProjectId,
                selectedSlug,
                "json",
                requestedEngines,
              )}
              class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-50 transition-colors"
              title="Download structured machine-readable JSON analysis report"
            >
              <Download class="w-3.5 h-3.5" />
              <span>JSON</span>
            </a>
          {/if}
        </div>
      </div>

      <!-- Filters & Search Bar -->
      <div class="grid grid-cols-1 sm:grid-cols-12 gap-3 pt-2">
        <!-- Search Input -->
        <div class="sm:col-span-6 relative">
          <Search
            class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2"
          />
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="Search findings by rule, GUID, title, or citation (e.g. NASA-STD, EN 1998)…"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-accent"
          />
        </div>

        <!-- Severity Filter -->
        <div class="sm:col-span-3">
          <select
            bind:value={severityFilter}
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 focus:outline-none focus:border-accent"
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 focus:outline-none focus:border-accent"
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
      <div
        class="flex items-center justify-between text-xs text-slate-400 px-1"
      >
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            bind:checked={showLowRisk}
            class="rounded border-slate-700 bg-slate-900 text-accent focus:ring-0 w-3.5 h-3.5"
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
      <div
        class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-950/50"
      >
        {#if sortedFilteredIssues.length === 0}
          <div class="p-12 text-center text-xs text-slate-500">
            No compliance issues match your selected filters.
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
              <thead
                class="bg-slate-950 border-b border-slate-800 text-caption uppercase tracking-wider text-slate-400 font-semibold"
              >
                <tr>
                  <th class="py-3.5 px-4 w-10">
                    <input
                      type="checkbox"
                      checked={allFilteredFindingsSelected}
                      on:change={toggleSelectAllFindings}
                      class="rounded bg-slate-950 border-slate-700 text-accent focus:ring-accent cursor-pointer w-4 h-4"
                      title="Select all findings"
                    />
                  </th>
                  <th
                    class="py-3.5 px-4 cursor-pointer hover:text-slate-50 transition-colors select-none"
                    on:click={() => toggleFindingSort("band")}
                  >
                    <div class="flex items-center gap-1">
                      <span>Severity</span>
                      {#if findingSortField === "band"}
                        {#if findingSortAsc}<ArrowUp class="w-3 h-3 text-accent" />{:else}<ArrowDown class="w-3 h-3 text-accent" />{/if}
                      {:else}
                        <ArrowUpDown class="w-3 h-3 text-slate-600" />
                      {/if}
                    </div>
                  </th>
                  <th
                    class="py-3.5 px-4 cursor-pointer hover:text-slate-50 transition-colors select-none"
                    on:click={() => toggleFindingSort("rule_id")}
                  >
                    <div class="flex items-center gap-1">
                      <span>Rule &amp; Mechanism</span>
                      {#if findingSortField === "rule_id"}
                        {#if findingSortAsc}<ArrowUp class="w-3 h-3 text-accent" />{:else}<ArrowDown class="w-3 h-3 text-accent" />{/if}
                      {:else}
                        <ArrowUpDown class="w-3 h-3 text-slate-600" />
                      {/if}
                    </div>
                  </th>
                  <th
                    class="py-3.5 px-4 cursor-pointer hover:text-slate-50 transition-colors select-none"
                    on:click={() => toggleFindingSort("element_id")}
                  >
                    <div class="flex items-center gap-1">
                      <span>Element GUID</span>
                      {#if findingSortField === "element_id"}
                        {#if findingSortAsc}<ArrowUp class="w-3 h-3 text-accent" />{:else}<ArrowDown class="w-3 h-3 text-accent" />{/if}
                      {:else}
                        <ArrowUpDown class="w-3 h-3 text-slate-600" />
                      {/if}
                    </div>
                  </th>
                  <th
                    class="py-3.5 px-4 cursor-pointer hover:text-slate-50 transition-colors select-none"
                    on:click={() => toggleFindingSort("title")}
                  >
                    <div class="flex items-center gap-1">
                      <span>Finding &amp; Citations</span>
                      {#if findingSortField === "title"}
                        {#if findingSortAsc}<ArrowUp class="w-3 h-3 text-accent" />{:else}<ArrowDown class="w-3 h-3 text-accent" />{/if}
                      {:else}
                        <ArrowUpDown class="w-3 h-3 text-slate-600" />
                      {/if}
                    </div>
                  </th>
                  <th
                    class="py-3.5 px-4 text-center cursor-pointer hover:text-slate-50 transition-colors select-none"
                    on:click={() => toggleFindingSort("score")}
                  >
                    <div class="flex items-center justify-center gap-1">
                      <span>Score / Clearance</span>
                      {#if findingSortField === "score"}
                        {#if findingSortAsc}<ArrowUp class="w-3 h-3 text-accent" />{:else}<ArrowDown class="w-3 h-3 text-accent" />{/if}
                      {:else}
                        <ArrowUpDown class="w-3 h-3 text-slate-600" />
                      {/if}
                    </div>
                  </th>
                  <th class="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each paginatedIssues as issue}
                  {@const isDq =
                    issue.mechanism === "data_quality" ||
                    issue.mechanism === "Data Quality"}
                  <tr class="hover:bg-slate-900/60 transition-colors group {selectedFindingIds.includes(issue.id) ? 'bg-blue-950/20' : ''}">
                    <!-- Row Checkbox -->
                    <td class="py-3.5 px-4 align-top w-10">
                      <input
                        type="checkbox"
                        checked={selectedFindingIds.includes(issue.id)}
                        on:change={() => toggleSelectFinding(issue.id)}
                        class="rounded bg-slate-950 border-slate-700 text-accent focus:ring-accent cursor-pointer w-4 h-4"
                      />
                    </td>

                    <!-- Severity Band Pill -->
                    <td class="py-3.5 px-4 align-top whitespace-nowrap">
                      {#if isDq}
                        <span
                          class="inline-block px-2.5 py-0.5 rounded-full text-micro font-semibold uppercase bg-slate-800 text-slate-300 border border-slate-700"
                        >
                          Data Quality
                        </span>
                      {:else if issue.band === "critical"}
                        <span
                          class="inline-block px-2.5 py-0.5 rounded-full text-micro font-semibold uppercase bg-red-950/80 text-red-400 border border-red-800/80 shadow-sm"
                        >
                          Critical
                        </span>
                      {:else if issue.band === "high"}
                        <span
                          class="inline-block px-2.5 py-0.5 rounded-full text-micro font-semibold uppercase bg-orange-950/80 text-orange-400 border border-orange-800/80 shadow-sm"
                        >
                          High
                        </span>
                      {:else if issue.band === "medium"}
                        <span
                          class="inline-block px-2.5 py-0.5 rounded-full text-micro font-semibold uppercase bg-yellow-950/80 text-yellow-400 border border-yellow-800/80 shadow-sm"
                        >
                          Medium
                        </span>
                      {:else}
                        <span
                          class="inline-block px-2.5 py-0.5 rounded-full text-micro font-semibold uppercase bg-emerald-950/80 text-emerald-400 border border-emerald-800/80 shadow-sm"
                        >
                          Low
                        </span>
                      {/if}
                    </td>

                    <!-- Rule & Mechanism -->
                    <td class="py-3.5 px-4 align-top font-mono">
                      <div class="font-bold text-slate-50 text-xs">
                        {issue.rule_id}
                      </div>
                      <div class="text-micro text-slate-400 mt-0.5">
                        {issue.mechanism}
                      </div>
                    </td>

                    <!-- Element GUID -->
                    <td class="py-3.5 px-4 align-top">
                      <div
                        class="flex items-center gap-1.5 font-mono text-slate-300 text-caption"
                      >
                        <span
                          class="truncate max-w-[140px]"
                          title={issue.element_id}>{issue.element_id}</span
                        >
                        <button
                          type="button"
                          on:click={() => copyText(issue.element_id)}
                          class="text-slate-500 hover:text-slate-50 transition-colors"
                          title="Copy GUID"
                        >
                          <Copy class="w-3 h-3" />
                        </button>
                      </div>
                      {#if issue.details?.ifc_type}
                        <div
                          class="text-micro text-slate-500 font-mono mt-0.5"
                        >
                          {issue.details.ifc_type}
                        </div>
                      {/if}
                    </td>

                    <!-- Finding, Mitigation, & Citations -->
                    <td class="py-3.5 px-4 align-top max-w-md">
                      <div class="font-semibold text-slate-100">
                        {issue.title}
                      </div>
                      {#if issue.mitigation}
                        <div
                          class="text-caption text-slate-400 mt-1 line-clamp-2"
                        >
                          {issue.mitigation}
                        </div>
                      {/if}

                      <!-- Real Citations -->
                      {#if issue.citations && issue.citations.length > 0}
                        <div class="flex flex-wrap items-center gap-1.5 mt-2">
                          {#each issue.citations as cit}
                            <span
                              class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-micro font-medium bg-slate-900 text-indigo-300 border border-indigo-900/60"
                              title={cit.reason}
                            >
                              <FileText class="w-2.5 h-2.5 opacity-70" />
                              <span>{cit.standard} {cit.clause}</span>
                            </span>
                          {/each}
                        </div>
                      {/if}
                    </td>

                    <!-- Score or Clearance Depth -->
                    <td class="py-3.5 px-4 align-top text-center font-mono">
                      {#if isDq}
                        <span class="text-slate-500 text-caption">N/A</span>
                      {:else if issue.score !== undefined && issue.score > 0}
                        <div class="text-xs font-bold text-slate-50">
                          {issue.score.toFixed(2)}
                        </div>
                        <div class="text-nano text-slate-500">Risk Score</div>
                      {:else if issue.details?.intrusion_depth_mm !== undefined}
                        <div class="text-xs font-bold text-red-400">
                          {issue.details.intrusion_depth_mm} mm
                        </div>
                        <div class="text-nano text-slate-500">
                          Clash Intrusion
                        </div>
                      {:else}
                        <span class="text-slate-500 text-caption">-</span>
                      {/if}
                    </td>

                    <!-- Action Buttons -->
                    <td
                      class="py-3.5 px-4 align-top text-right whitespace-nowrap space-x-1.5"
                    >
                      <button
                        type="button"
                        on:click={() => (inspectedIssue = issue)}
                        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-50 text-xs font-semibold transition-colors"
                      >
                        <span>Details</span>
                      </button>

                      {#if selectedProjectId && issue.element_id}
                        <button
                          type="button"
                          on:click={() =>
                            onSelectProjectForViewer(
                              selectedProjectId!,
                              issue.element_id,
                            )}
                          class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent hover:text-blue-300 text-xs font-semibold transition-colors"
                        >
                          <ScanEye class="w-3.5 h-3.5" />
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
  {:else if !isRunning}
    <div
      class="p-16 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl space-y-3"
    >
      <div
        class="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-slate-400"
      >
        <Compass class="w-6 h-6" />
      </div>
      <div>
        <div class="text-sm font-bold text-slate-50">No Analysis Run Loaded</div>
        <div class="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
          Select an OpenBIM project above and click <strong>"Run Audit"</strong>
          to compute compliance across corrosion engines or Blue Halo seismic clearance
          envelopes.
        </div>
      </div>
    </div>
  {/if}
</div>

<!-- Detailed Issue Inspection Modal / Drawer -->
{#if inspectedIssue}
  {@const isDq =
    inspectedIssue.mechanism === "data_quality" ||
    inspectedIssue.mechanism === "Data Quality"}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200"
  >
    <div
      class="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
    >
      <!-- Modal Header -->
      <div
        class="p-5 border-b border-slate-800 flex items-center justify-between"
      >
        <div class="flex items-center gap-2.5">
          <span
            class="px-2.5 py-1 rounded-md bg-slate-800 text-slate-50 font-mono text-xs font-bold border border-slate-700"
          >
            {inspectedIssue.id}
          </span>
          <span class="text-sm font-bold text-slate-50"
            >{inspectedIssue.rule_id}</span
          >
          {#if isDq}
            <span
              class="px-2 py-0.5 rounded text-micro font-semibold uppercase bg-slate-800 text-slate-300 border border-slate-700"
            >
              Data Quality
            </span>
          {:else}
            <span
              class="px-2 py-0.5 rounded text-micro font-semibold uppercase {inspectedIssue.band ===
              'critical'
                ? 'bg-red-950/80 text-red-400'
                : inspectedIssue.band === 'high'
                  ? 'bg-orange-950/80 text-orange-400'
                  : inspectedIssue.band === 'medium'
                    ? 'bg-yellow-950/80 text-yellow-400'
                    : 'bg-emerald-950/80 text-emerald-400'}"
            >
              {inspectedIssue.band}
            </span>
          {/if}
        </div>
        <button
          type="button"
          on:click={() => (inspectedIssue = null)}
          class="p-1 rounded-lg text-slate-400 hover:text-slate-50 hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Modal Body -->
      <div class="p-6 space-y-6 overflow-y-auto">
        <!-- Title & Mechanism -->
        <div>
          <h3 class="text-base font-bold text-slate-50">{inspectedIssue.title}</h3>
          <p class="text-xs text-slate-400 mt-1">
            Mechanism: <strong class="text-slate-200"
              >{inspectedIssue.mechanism}</strong
            >
          </p>
        </div>

        <!-- Element Context Card -->
        <div
          class="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2"
        >
          <div
            class="text-xs uppercase font-bold tracking-wider text-slate-400"
          >
            Target IFC Element
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span class="text-slate-500">GlobalId (GUID):</span>
              <div
                class="font-mono text-slate-200 flex items-center gap-1.5 mt-0.5"
              >
                <span class="truncate">{inspectedIssue.element_id}</span>
                <button
                  type="button"
                  on:click={() => copyText(inspectedIssue?.element_id || "")}
                  class="text-slate-400 hover:text-slate-50"
                >
                  <Copy class="w-3 h-3" />
                </button>
              </div>
            </div>
            {#if inspectedIssue.assignee_role}
              <div>
                <span class="text-slate-500">Assigned Resolution Role:</span>
                <div class="font-semibold text-slate-200 mt-0.5">
                  {inspectedIssue.assignee_role}
                </div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Description & Mitigations -->
        {#if inspectedIssue.description}
          <div class="space-y-1">
            <h4
              class="text-xs uppercase font-bold tracking-wider text-slate-400"
            >
              Finding Description
            </h4>
            <p
              class="text-xs text-slate-300 bg-slate-950/40 p-3 rounded-xl border border-slate-800/60"
            >
              {inspectedIssue.description}
            </p>
          </div>
        {/if}

        {#if inspectedIssue.mitigation}
          <div class="space-y-1">
            <h4
              class="text-xs uppercase font-bold tracking-wider text-emerald-400"
            >
              Engineering Mitigation Guidance
            </h4>
            <p
              class="text-xs text-emerald-200 bg-emerald-950/30 p-3 rounded-xl border border-emerald-800/40"
            >
              {inspectedIssue.mitigation}
            </p>
          </div>
        {/if}

        <!-- Standards Cited (White Box Audit Trail) -->
        {#if inspectedIssue.citations && inspectedIssue.citations.length > 0}
          <div class="space-y-2">
            <h4
              class="text-xs uppercase font-bold tracking-wider text-indigo-400"
            >
              White Box Audit Citations
            </h4>
            <div class="space-y-2">
              {#each inspectedIssue.citations as cit}
                <div
                  class="p-3 rounded-xl bg-indigo-950/20 border border-indigo-800/40 text-xs"
                >
                  <div
                    class="font-bold text-indigo-300 flex items-center gap-1.5"
                  >
                    <FileText class="w-3.5 h-3.5" />
                    <span>{cit.standard} — {cit.clause}</span>
                  </div>
                  {#if cit.reason}
                    <div class="text-caption text-slate-300 mt-1">
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
            <h4
              class="text-xs uppercase font-bold tracking-wider text-slate-400"
            >
              Metadata Parameters
            </h4>
            <pre
              class="text-caption font-mono text-slate-400 bg-slate-950 p-3 rounded-xl border border-slate-800 overflow-x-auto">{JSON.stringify(
                inspectedIssue.details,
                null,
                2,
              )}</pre>
          </div>
        {/if}
      </div>

      <!-- Modal Footer -->
      <div
        class="p-4 border-t border-slate-800 flex items-center justify-between bg-slate-950/40"
      >
        <button
          type="button"
          on:click={() => (inspectedIssue = null)}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-50 transition-colors"
        >
          Close
        </button>

        {#if selectedProjectId && inspectedIssue.element_id}
          <button
            type="button"
            on:click={() => {
              const elId = inspectedIssue?.element_id;
              inspectedIssue = null;
              if (selectedProjectId && elId) {
                onSelectProjectForViewer(selectedProjectId, elId);
              }
            }}
            class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-accent hover:bg-accent-hover text-white transition-colors"
          >
            <ScanEye class="w-4 h-4" />
            <span>Isolate in 3D Viewer</span>
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- IFC Upload Modal -->
{#if isUploadModalOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200"
  >
    <div
      class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4"
    >
      <div class="flex items-center justify-between">
        <h3 class="text-base font-bold text-slate-50">Upload IFC Model</h3>
        <button
          type="button"
          on:click={() => (isUploadModalOpen = false)}
          class="text-slate-400 hover:text-slate-50"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <p class="text-xs text-slate-400">
        Attach or update the IFC model for <strong
          >{currentProject?.name}</strong
        > (Session A file lineage with SHA-256 digest).
      </p>

      <div
        class="border-2 border-dashed border-slate-700 rounded-2xl p-6 text-center hover:border-slate-500 transition-colors"
      >
        <Upload class="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <input
          type="file"
          accept=".ifc"
          on:change={(e) => (uploadFile = e.currentTarget.files?.[0] || null)}
          class="text-xs text-slate-300 file:mr-3 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-accent file:text-white hover:file:bg-accent-hover"
        />
      </div>

      {#if uploadSuccessMsg}
        <div
          class="p-3 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs"
        >
          {uploadSuccessMsg}
        </div>
      {/if}

      {#if uploadErrorMsg}
        <div
          class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs"
        >
          {uploadErrorMsg}
        </div>
      {/if}

      <div class="flex items-center justify-end gap-2 pt-2">
        <button
          type="button"
          on:click={() => (isUploadModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={!uploadFile || isUploading}
          on:click={handleUploadIfc}
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-accent text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {#if isUploading}
            <RefreshCw class="w-3.5 h-3.5 animate-spin" />
            <span>Uploading…</span>
          {:else}
            <span>Confirm Upload</span>
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
