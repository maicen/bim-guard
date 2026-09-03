<script lang="ts">
  import { run, stopPropagation } from "svelte/legacy";

  import { onMount, untrack } from "svelte";
  import {
    Play,
    ScanEye,
    Download,
    Timer,
    ChevronDown,
    ChevronRight,
    Building2,
    DoorOpen,
    Layers,
    Flame,
    ArrowUpRight,
    Droplets,
    Car,
    Footprints,
    Wind,
    Sparkles,
    FolderOpen,
    CheckCircle2,
    Save,
  } from "lucide-svelte";
  import { projectsApi, analyzeApi, lineageApi, rulesApi } from "../lib/api";
  import ProjectEnhancementsModal from "../lib/components/ProjectEnhancementsModal.svelte";
  import BsddBadge from "../lib/components/BsddBadge.svelte";
  import type {
    Project,
    ArchAnalysisResult,
    RuleComplianceResult,
    RuleElementResult,
    BuildingSummary,
    ExitCountResult,
    TravelDistanceResult,
    DaylightResult,
    FireSeparationResult,
    GarageResult,
    RuleFolder,
  } from "../lib/types";

  interface Props {
    initialProjectId?: number | null;
  }

  let { initialProjectId = null }: Props = $props();

  let projects: Project[] = $state([]);
  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  let isRunning = $state(false);
  let error = $state("");
  let result: ArchAnalysisResult | null = $state(null);

  // Rule folder selection — '' means "All rules"
  let ruleFolders: RuleFolder[] = $state([]);
  let selectedFolder = $state(""); // '' = All
  let isFoldersLoading = $state(false);

  // Enhanced model gate
  let hasEnhancedModel: boolean | null = $state(null);
  let isCheckingEnhancement = $state(false);
  let showEnhancementsModal = $state(false);

  // BCF save tracking (backend auto-persists; we reflect the status)
  let bcfSaveMessage = $state("");
  let bcfSaveType: "success" | "error" = $state("success");

  let prevArchKey = $state("");

  // Collapsible state tracking
  let openDomains: Record<string, boolean> = $state({});
  let openRules: Record<string, boolean> = $state({});
  let openSections: Record<string, boolean> = $state({});

  onMount(async () => {
    // Load projects and rule folders in parallel; do NOT auto-run analysis
    try {
      const [projectData] = await Promise.all([projectsApi.list(), loadFolders()]);
      projects = projectData.projects || [];
      const archProjs = projects.filter(
        (p) =>
          p.analysis_type === "Arch" ||
          p.analysis_type === "Architectural" ||
          p.analysis_type === "Architecture",
      );
      if (!selectedProjectId && archProjs.length > 0) {
        selectedProjectId = archProjs[0].id;
      }
      // Only check for enhanced model — do not auto-run
      if (selectedProjectId) {
        await checkEnhancedModel();
      }
    } catch (err: any) {
      error = err.message || "Failed to load projects";
    }
  });

  async function loadFolders(): Promise<void> {
    isFoldersLoading = true;
    try {
      ruleFolders = await rulesApi.folders("Arch");
    } catch {
      ruleFolders = [];
    } finally {
      isFoldersLoading = false;
    }
  }

  /** Check for enhanced model only — do NOT run analysis. */
  async function checkEnhancedModel() {
    if (!selectedProjectId) return;
    isCheckingEnhancement = true;
    hasEnhancedModel = null;
    try {
      const history = await lineageApi.getHistory(selectedProjectId);
      hasEnhancedModel = Array.isArray(history) && history.length > 0;
    } catch {
      hasEnhancedModel = false;
    } finally {
      isCheckingEnhancement = false;
    }
  }

  /** Called when the project selector changes — reset state, check enhancement. */
  async function handleProjectChange() {
    result = null;
    error = "";
    bcfSaveMessage = "";
    await checkEnhancedModel();
    if (!hasEnhancedModel) {
      showEnhancementsModal = true;
    }
  }

  /**
   * Main run entrypoint — validates enhanced model, then runs the ARCH audit.
   * Only called by the Run button, never automatically.
   */
  async function handleRunClick() {
    if (!selectedProjectId) return;
    if (!hasEnhancedModel) {
      await checkEnhancedModel();
      if (!hasEnhancedModel) {
        showEnhancementsModal = true;
        return;
      }
    }
    await runCheck();
  }

  // Opens the 3D Viewer in its own browser tab instead of navigating away
  // from these results in-app, so a reviewer can keep the audit open
  // alongside the model. Relies on App.svelte's existing /viewer deep-link
  // handler (applyDeepLinkFromLocation), which reads these same query params.
  function openViewerInNewTab(projectId: number, elementGuid?: string, bcfArtifactId?: number) {
    // A one-shot builder for a URL string, never read reactively, so the
    // plain built-in is correct here.
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const params = new URLSearchParams();
    params.set("project_id", String(projectId));
    if (elementGuid) params.set("element_guid", elementGuid);
    if (bcfArtifactId) params.set("bcf_artifact_id", String(bcfArtifactId));
    window.open(`/viewer?${params.toString()}`, "_blank");
  }

  async function runCheck() {
    if (!selectedProjectId) return;
    isRunning = true;
    error = "";
    bcfSaveMessage = "";
    try {
      result = await analyzeApi.runArch(selectedProjectId, selectedFolder);
      if (result) {
        initDomainState(result);
        if (result.bcf_artifact_id) {
          bcfSaveMessage = `BCF report saved to database (artifact #${result.bcf_artifact_id})`;
          bcfSaveType = "success";
        } else if (result.total_issues > 0) {
          bcfSaveMessage = "BCF report auto-persistence encountered an issue.";
          bcfSaveType = "error";
        }
      }
    } catch (err: any) {
      error = err.message || "Architectural compliance check failed.";
    } finally {
      isRunning = false;
    }
  }

  /**
   * Called when the enhancements modal is closed.
   * Re-checks enhancement status; user must click Run explicitly.
   */
  async function handleEnhancementsModalClose() {
    showEnhancementsModal = false;
    if (!selectedProjectId) return;
    try {
      const history = await lineageApi.getHistory(selectedProjectId);
      hasEnhancedModel = Array.isArray(history) && history.length > 0;
    } catch {
      hasEnhancedModel = false;
    }
    // Do NOT auto-run — wait for user to click Run
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  function formatDuration(seconds?: number | null): string {
    if (seconds === undefined || seconds === null) return "";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);
    return `${minutes}m ${rest}s`;
  }

  function fmtVal(v: any): string {
    if (v === null || v === undefined) return "—";
    if (typeof v === "number") {
      return v >= 1 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v.toFixed(4);
    }
    return String(v);
  }

  function ruleRequiredText(rule: RuleComplianceResult): string {
    const op = rule.operator || "";
    const cv = rule.check_value;
    const unit = rule.unit || "";
    if (op === ">=") return `≥ ${cv} ${unit}`.trim();
    if (op === "<=") return `≤ ${cv} ${unit}`.trim();
    if (op === "between") return `${rule.value_min}–${rule.value_max} ${unit}`.trim();
    if (op === "exists") return "must be present";
    if (op === "not_exists") return "must not be present";
    return cv !== null && cv !== undefined ? `${op} ${cv} ${unit}`.trim() : "—";
  }

  const ELEM_LABELS: Record<string, string> = {
    IfcDoor: "Doors",
    IfcWindow: "Windows",
    IfcStairFlight: "Stair Flights",
    IfcRailing: "Railings",
    IfcRamp: "Ramps",
    IfcRampFlight: "Ramp Flights",
    IfcSanitaryTerminal: "Sanitary Terminals",
    IfcAlarm: "Alarms",
    IfcWall: "Walls",
    IfcSlab: "Slabs",
    IfcSpace: "Spaces",
    IfcBuildingStorey: "Storeys",
  };

  // Category → IFC target classes (matching the legacy _SIMPLE_CATEGORY_TARGETS)
  const DOMAIN_TARGETS: Record<string, string[]> = {
    windows: ["IfcWindow"],
    doors: ["IfcDoor"],
    stairs: ["IfcStairFlight", "IfcRailing"],
    ramps: ["IfcRamp", "IfcRampFlight"],
    washrooms: ["IfcSanitaryTerminal"],
    fire: ["IfcAlarm"],
  };

  interface DomainConfig {
    key: string;
    label: string;
    targets: string[];
    category: string;
  }

  const DOMAIN_CARDS: DomainConfig[] = [
    { key: "windows", label: "Windows & Glazing", targets: ["IfcWindow"], category: "windows" },
    { key: "doors", label: "Doors", targets: ["IfcDoor"], category: "doors" },
    {
      key: "stairs",
      label: "Stairs, Guards & Handrails",
      targets: ["IfcStairFlight", "IfcRailing"],
      category: "stairs",
    },
    { key: "ramps", label: "Ramps", targets: ["IfcRamp", "IfcRampFlight"], category: "ramps" },
    { key: "egress", label: "Means of Egress", targets: [], category: "egress" },
    {
      key: "washrooms",
      label: "Washrooms & Accessibility",
      targets: ["IfcSanitaryTerminal"],
      category: "washrooms",
    },
    { key: "plumbing", label: "Plumbing Fixture Counts", targets: [], category: "plumbing" },
    {
      key: "fire",
      label: "Fire Protection (House-Level)",
      targets: ["IfcAlarm"],
      category: "fire",
    },
    { key: "garage", label: "Garage / Carport", targets: [], category: "garage" },
  ];

  function getDomainRules(targets: string[]): RuleComplianceResult[] {
    if (!result?.rule_compliance) return [];
    return result.rule_compliance.filter((r) => targets.includes(r.target || ""));
  }

  function domainBadge(rules: RuleComplianceResult[]): { label: string; cls: string } {
    if (!rules.length) return { label: "N/A", cls: "bg-slate-800 text-slate-400 border-slate-700" };
    const real = rules.filter((r) => r.status !== "NO_ELEMENTS");
    if (!real.length) return { label: "N/A", cls: "bg-slate-800 text-slate-400 border-slate-700" };
    const nFail = real.filter((r) => r.status === "FAIL").length;
    if (nFail)
      return {
        label: `${nFail} rule(s) failed`,
        cls: "bg-rose-950/80 text-rose-300 border-rose-800",
      };
    if (real.some((r) => ["MISSING_DATA", "PARTIAL"].includes(r.status || "")))
      return { label: "Missing data", cls: "bg-amber-950/80 text-amber-300 border-amber-800" };
    return { label: "All pass", cls: "bg-emerald-950/80 text-emerald-300 border-emerald-800" };
  }

  function initDomainState(r: ArchAnalysisResult) {
    const rc = r.rule_compliance || [];
    for (const dc of DOMAIN_CARDS) {
      const rules = rc.filter((rule) => dc.targets.includes(rule.target || ""));
      const hasFail = rules.some((rule) => rule.status === "FAIL");
      openDomains[dc.key] = hasFail;
    }
    // Egress / fire / garage open if they have failures
    const eg = r.egress_checks || {};
    const exitResults = eg.exit_count?.results || [];
    const travel = eg.travel_distance || [];
    if ([...exitResults, ...travel].some((x: any) => !x.passes)) openDomains["egress"] = true;
    const fireSep = (r.spatial_checks || {}).fire_separation || [];
    if (fireSep.some((x: any) => !x.passes)) openDomains["fire"] = true;
  }

  function toggleDomain(key: string) {
    openDomains[key] = !openDomains[key];
    openDomains = openDomains;
  }

  function toggleRule(key: string) {
    openRules[key] = !openRules[key];
    openRules = openRules;
  }

  function toggleSection(key: string) {
    openSections[key] = !openSections[key];
    openSections = openSections;
  }

  let relevantProjects = $derived(
    projects.filter(
      (p) =>
        p.analysis_type === "Arch" ||
        p.analysis_type === "Architectural" ||
        p.analysis_type === "Architecture",
    ),
  );
  let currentArchKey = $derived(relevantProjects.map((p) => p.id).join(","));
  run(() => {
    if (relevantProjects.length > 0 && currentArchKey !== prevArchKey) {
      prevArchKey = currentArchKey;
      if (!selectedProjectId || !relevantProjects.some((p) => p.id === selectedProjectId)) {
        selectedProjectId = relevantProjects[0].id;
        checkEnhancedModel();
      }
    }
  });
  let selectedProject = $derived(relevantProjects.find((p) => p.id === selectedProjectId) || null);
  // ── Reactive derivations ────────────────────────────────────────────────

  let summary = $derived(result?.rule_compliance_summary || {});
  let passRate = $derived(summary.pass_rate !== undefined ? Number(summary.pass_rate) : null);
  let durationSeconds = $derived(summary.duration_seconds);
  let uniqueElements = $derived(summary.unique_elements_evaluated || 0);
  let rulesWithElements = $derived(summary.rules_with_elements || 0);
  let totalRules = $derived(summary.total_rules || 0);
  let buildingSummary = $derived(result?.building_summary);
  let folderNote = $derived(
    result?.rule_folder ? ` · ${result.rule_folder}` : selectedFolder ? ` · ${selectedFolder}` : "",
  );
  // The subtitle used to be a hardcoded "Ontario Building Code Part 9" claim,
  // which goes wrong the moment someone scopes the audit to a custom ruleset
  // (e.g. door_mock) that has nothing to do with OBC.
  let selectedFolderDisplayName = $derived(
    ruleFolders.find((f) => f.ruleset_id === selectedFolder)?.display_name || selectedFolder,
  );
</script>

<div class="mx-auto max-w-7xl space-y-5">
  <!-- ═══ Header ═══ -->
  <div>
    <div class="mb-1 text-xs font-bold uppercase tracking-widest text-slate-400">Analysis</div>
    <h1 class="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">
      {#if result}
        {result.project_name} — ARCH Analysis{folderNote}
      {:else}
        Architectural Compliance Audit
      {/if}
    </h1>
    <p class="mt-1 text-xs text-slate-400 sm:text-sm">
      {#if selectedFolder}
        Domain-based compliance check against the <strong class="font-mono text-slate-300"
          >{selectedFolderDisplayName}</strong
        > ruleset.
      {:else}
        Domain-based compliance check against Ontario Building Code Part 9 and every other loaded
        architectural ruleset.
      {/if}
    </p>

    <!-- Pass rate pill + coverage evidence -->
    {#if result && totalRules > 0}
      <div class="mt-3 flex flex-wrap items-center gap-3">
        {#if passRate !== null}
          <span
            class="inline-block rounded-full border px-3 py-1 text-xs font-bold tracking-wide {passRate >=
            80
              ? 'border-emerald-800 bg-emerald-950/80 text-emerald-300'
              : passRate >= 50
                ? 'border-amber-800 bg-amber-950/80 text-amber-300'
                : 'border-rose-800 bg-rose-950/80 text-rose-300'}"
          >
            {passRate.toFixed(0)}% pass rate
          </span>
        {/if}
        {#if durationSeconds !== undefined && durationSeconds !== null}
          <span class="inline-flex items-center gap-1 font-mono text-xs text-slate-400">
            <Timer class="h-3.5 w-3.5 text-blue-400" />
            ⏱ {formatDuration(durationSeconds)}
          </span>
        {/if}
        {#if uniqueElements > 0}
          <span class="text-xs text-slate-400">
            🔍 <strong class="text-slate-300">{uniqueElements}</strong> element(s) checked across
            <strong class="text-slate-300">{rulesWithElements}</strong> applicable rule(s) — every match
            evaluated, no sampling
          </span>
        {/if}
      </div>
    {/if}
  </div>

  <!-- ═══ Project Selector ═══ -->
  <div
    class="flex flex-col gap-3 rounded-2xl border border-accent/40 bg-slate-900/50 p-4 sm:flex-row sm:items-center"
  >
    <div class="flex shrink-0 items-center gap-2">
      <Building2 class="h-4 w-4 text-accent" />
      <span class="text-xs font-bold text-slate-300">Project</span>
    </div>
    <div class="relative flex-1 sm:max-w-xs">
      <select
        bind:value={selectedProjectId}
        onchange={handleProjectChange}
        class="w-full appearance-none rounded-lg border border-slate-700 bg-slate-800/60 py-1.5 pl-3 pr-8 text-xs font-medium text-slate-50 focus:border-accent focus:outline-none"
      >
        {#if relevantProjects.length === 0}
          <option value={null}>No Arch projects found</option>
        {:else}
          {#each relevantProjects as project (project.id)}
            <option value={project.id}>{project.name}</option>
          {/each}
        {/if}
      </select>
      <ChevronDown
        class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
      />
    </div>
  </div>

  <!-- ═══ Ruleset Folder Selector ═══ -->
  {#if selectedProjectId}
    <div
      class="flex flex-col gap-3 rounded-2xl border border-accent/40 bg-slate-900/50 p-4 sm:flex-row sm:items-center"
    >
      <div class="flex shrink-0 items-center gap-2">
        <FolderOpen class="h-4 w-4 text-accent" />
        <span class="text-xs font-bold text-slate-300">Ruleset</span>
      </div>
      <div class="relative flex-1 sm:max-w-xs">
        <select
          bind:value={selectedFolder}
          disabled={isFoldersLoading}
          class="w-full appearance-none rounded-lg border border-slate-700 bg-slate-800/60 py-1.5 pl-3 pr-8 text-xs font-medium text-slate-50 focus:border-accent focus:outline-none disabled:opacity-60"
        >
          <option value="">{isFoldersLoading ? "Loading folders…" : "All Rules"}</option>
          {#each ruleFolders as folder (folder)}
            <option value={folder.ruleset_id}>{folder.display_name}</option>
          {/each}
        </select>
        <ChevronDown
          class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
        />
      </div>
      {#if selectedFolder}
        <span class="shrink-0 text-micro text-slate-500"
          >Selected: <span class="font-mono text-slate-300">{selectedFolder}</span> (scopes audit to this
          ruleset only)</span
        >
      {:else}
        <span class="shrink-0 text-micro text-slate-500"
          >Scope: <span class="text-slate-300">All building code rules</span></span
        >
      {/if}
    </div>
  {/if}

  <!-- ═══ Run Analysis Bar ═══ -->
  <div class="flex flex-wrap items-center gap-2.5">
    {#if result && selectedProjectId}
      <button
        type="button"
        onclick={() =>
          selectedProjectId &&
          openViewerInNewTab(selectedProjectId, undefined, result?.bcf_artifact_id || undefined)}
        class="inline-flex items-center gap-1.5 rounded-xl border border-emerald-700 bg-emerald-800/80 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-emerald-700"
        title="Open in 3D ThatOpen Viewer with error viewpoints"
      >
        <ScanEye class="h-3.5 w-3.5" />
        View in 3D / BCF
      </button>
      {#if result.bcf_artifact_id}
        <a
          href={analyzeApi.getBcfArtifactUrl(result.bcf_artifact_id)}
          download
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-700"
        >
          <Download class="h-3.5 w-3.5" />
          BCF
        </a>
      {/if}
    {/if}

    <button
      type="button"
      disabled={isRunning || isCheckingEnhancement || !selectedProjectId}
      onclick={handleRunClick}
      class="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50"
    >
      <Play class="h-3.5 w-3.5" />
      {isRunning ? "Auditing…" : isCheckingEnhancement ? "Checking model…" : "Run ARCH Audit"}
    </button>
  </div>

  {#if error}
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
      {error}
    </div>
  {/if}

  {#if bcfSaveMessage}
    <div
      class="flex items-center gap-2 rounded-xl p-3.5 text-xs
      {bcfSaveType === 'success'
        ? 'border border-emerald-800 bg-emerald-950/40 text-emerald-300'
        : 'border border-rose-800 bg-rose-950/40 text-rose-300'}"
    >
      <CheckCircle2
        class="h-4 w-4 shrink-0 {bcfSaveType === 'success' ? 'text-emerald-400' : 'text-rose-400'}"
      />
      <span>{bcfSaveMessage}</span>
      {#if result?.bcf_artifact_id}
        <a
          href={analyzeApi.getBcfArtifactUrl(result.bcf_artifact_id)}
          download
          class="ml-auto inline-flex items-center gap-1 rounded-lg border border-emerald-700 bg-emerald-900/60 px-2.5 py-1 text-emerald-200 transition-colors hover:bg-emerald-800"
        >
          <Download class="h-3 w-3" />
          Download BCF
        </a>
      {/if}
    </div>
  {/if}

  {#if hasEnhancedModel === false && !isCheckingEnhancement}
    <!-- No enhanced model warning banner -->
    <div
      class="flex items-start gap-3 rounded-2xl border border-purple-800/60 bg-purple-950/40 p-4"
    >
      <div
        class="shrink-0 rounded-xl border border-purple-500/20 bg-purple-500/10 p-2 text-purple-400"
      >
        <Sparkles class="h-4 w-4" />
      </div>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold text-purple-200">Enhanced model required</p>
        <p class="mt-0.5 text-xs text-purple-400">
          ARCH analysis runs on an enhanced/improved model. This project doesn't have one yet.
          Generate an improved model version to unlock the full compliance audit.
        </p>
      </div>
      <button
        type="button"
        onclick={() => (showEnhancementsModal = true)}
        class="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-purple-600 px-4 py-2 text-xs font-semibold text-white transition-all hover:scale-[1.02] hover:bg-purple-500"
      >
        <Sparkles class="h-3.5 w-3.5" />
        Run Improvements
      </button>
    </div>
  {/if}

  {#if result}
    <!-- ═══ Building Overview card ═══ -->
    {#if buildingSummary && (buildingSummary.storey_count || buildingSummary.room_count)}
      <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
        <!-- Header -->
        <button
          type="button"
          class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-800/30"
          onclick={() => toggleSection("building")}
        >
          <h2 class="flex items-center gap-2 text-sm font-bold text-slate-50">
            <Building2 class="h-4 w-4 text-blue-400" />
            Building Overview
          </h2>
          {#if openSections["building"]}
            <ChevronDown class="h-4 w-4 text-slate-400" />
          {:else}
            <ChevronRight class="h-4 w-4 text-slate-400" />
          {/if}
        </button>

        <!-- Stat strip (always visible) -->
        <div class="grid grid-cols-2 gap-3 px-4 pb-4 sm:grid-cols-4">
          <div class="rounded-xl bg-slate-800/60 px-4 py-3 text-center">
            <span class="block text-2xl font-bold text-slate-50"
              >{buildingSummary.storey_count || 0}</span
            >
            <span class="text-xs text-slate-400">Storeys</span>
          </div>
          <div class="rounded-xl bg-slate-800/60 px-4 py-3 text-center">
            <span class="block text-2xl font-bold text-slate-50"
              >{buildingSummary.room_count || 0}</span
            >
            <span class="text-xs text-slate-400">Rooms / Spaces</span>
          </div>
          <div class="rounded-xl bg-slate-800/60 px-4 py-3 text-center">
            <span class="block text-2xl font-bold text-slate-50">
              {buildingSummary.total_gfa_m2
                ? buildingSummary.total_gfa_m2.toLocaleString(undefined, {
                    maximumFractionDigits: 1,
                  })
                : "—"}
            </span>
            <span class="text-xs text-slate-400">GFA m²</span>
          </div>
          <div class="rounded-xl bg-slate-800/60 px-4 py-3 text-center">
            <span class="block text-2xl font-bold text-slate-50"
              >{buildingSummary.external_door_count || 0}</span
            >
            <span class="text-xs text-slate-400">Exit Doors</span>
          </div>
        </div>

        {#if openSections["building"]}
          <div class="space-y-4 px-4 pb-5">
            <!-- Floor breakdown table -->
            {#if buildingSummary.storeys && buildingSummary.storeys.length}
              {@const floorHeightMap = Object.fromEntries(
                (buildingSummary.floor_heights || []).map((h) => [h.from, h.height_mm]),
              )}
              <div>
                <h3 class="mb-2 text-xs font-semibold text-slate-300">Floor Breakdown</h3>
                <div class="max-h-64 overflow-auto rounded-lg border border-slate-800">
                  <table class="w-full text-xs">
                    <thead>
                      <tr class="bg-slate-800/80">
                        <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                          >Storey</th
                        >
                        <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                          >Floor-to-Floor</th
                        >
                        <th class="px-3 py-2 text-center text-xs font-semibold text-slate-400"
                          >Rooms</th
                        >
                        <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400"
                          >Area m²</th
                        >
                      </tr>
                    </thead>
                    <tbody>
                      {#each buildingSummary.storeys as s (s.name)}
                        {@const ri = buildingSummary.rooms_per_storey?.[s.name]}
                        {@const hMm = floorHeightMap[s.name]}
                        <tr class="border-b border-slate-800/60 last:border-0">
                          <td class="px-3 py-2 text-xs font-medium text-slate-50">{s.name}</td>
                          <td class="px-3 py-2 font-mono text-xs text-slate-300">
                            {#if hMm}
                              {hMm >= 1000
                                ? `${(hMm / 1000).toFixed(2)} m`
                                : `${hMm.toLocaleString()} mm`}
                            {:else}—{/if}
                          </td>
                          <td class="px-3 py-2 text-center text-xs text-slate-300"
                            >{ri?.count || "—"}</td
                          >
                          <td class="px-3 py-2 text-right font-mono text-xs text-slate-300">
                            {ri?.total_area_m2
                              ? ri.total_area_m2.toLocaleString(undefined, {
                                  maximumFractionDigits: 1,
                                })
                              : "—"}
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              </div>
            {/if}

            <!-- Element count badges -->
            {#if buildingSummary.element_counts && Object.keys(buildingSummary.element_counts).length}
              <div>
                <h3 class="mb-2 text-xs font-semibold text-slate-300">Elements Found</h3>
                <div class="flex flex-wrap gap-2">
                  {#each Object.entries(buildingSummary.element_counts).sort( ([a], [b]) => (ELEM_LABELS[a] || a).localeCompare(ELEM_LABELS[b] || b) ) as [k, v] (k)}
                    <span
                      class="inline-block rounded-full border border-blue-800/60 bg-blue-950/60 px-2.5 py-1 text-xs font-medium text-blue-300"
                    >
                      {ELEM_LABELS[k] || k}: {v}
                    </span>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Fixture count badges -->
            {#if buildingSummary.fixture_counts && Object.keys(buildingSummary.fixture_counts).length}
              <div>
                <h3 class="mb-2 text-xs font-semibold text-slate-300">Plumbing Fixtures</h3>
                <div class="flex flex-wrap gap-2">
                  {#each Object.entries(buildingSummary.fixture_counts).sort() as [k, v] (k)}
                    <span
                      class="inline-block rounded-full border border-cyan-800/60 bg-cyan-950/60 px-2.5 py-1 text-xs font-medium text-cyan-300"
                    >
                      {k}: {v}
                    </span>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Alarm count badges -->
            {#if buildingSummary.alarm_counts && Object.keys(buildingSummary.alarm_counts).length}
              <div>
                <h3 class="mb-2 text-xs font-semibold text-slate-300">Fire / CO Alarms</h3>
                <div class="flex flex-wrap gap-2">
                  {#each Object.entries(buildingSummary.alarm_counts).sort() as [k, v] (k)}
                    <span
                      class="inline-block rounded-full border border-rose-800/60 bg-rose-950/60 px-2.5 py-1 text-xs font-medium text-rose-300"
                    >
                      {k}: {v}
                    </span>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- QA warnings -->
            {#if (buildingSummary.unplaced_rooms?.length || 0) > 0 || (buildingSummary.unnamed_elements?.length || 0) > 0}
              <div>
                <h3 class="mb-2 text-xs font-semibold text-slate-300">Model QA</h3>
                <div class="space-y-1 rounded-lg border border-amber-800/40 bg-amber-950/30 p-3">
                  {#if (buildingSummary.unplaced_rooms?.length || 0) > 0}
                    <p class="text-xs text-amber-300">
                      ⚠ {buildingSummary.unplaced_rooms?.length} unplaced room(s) — not assigned to any
                      storey
                    </p>
                  {/if}
                  {#each buildingSummary.unnamed_elements || [] as u (u)}
                    <p class="text-xs text-amber-300">
                      ⚠ {u.count}
                      {ELEM_LABELS[u.type] || u.type} element(s) missing Name property
                    </p>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- ═══ Domain cards ═══ -->
    {#each DOMAIN_CARDS as domain (domain.key)}
      {@const rules = getDomainRules(domain.targets)}
      {@const badge = domainBadge(rules)}
      {@const isOpen = openDomains[domain.key] || false}

      <!-- Special handling for domains with non-rule-compliance data -->
      {#if domain.key === "egress"}
        <!-- Egress domain card -->
        {@const exitData = result.egress_checks?.exit_count || {}}
        {@const travel = result.egress_checks?.travel_distance || []}
        {@const exitResults = exitData.results || []}
        {@const allPasses = [...exitResults, ...travel]}
        {@const eFail = allPasses.filter((x) => !x.passes).length}
        {@const eBadge =
          allPasses.length === 0
            ? { label: "N/A", cls: "bg-slate-800 text-slate-400 border-slate-700" }
            : eFail > 0
              ? {
                  label: `${eFail} check(s) failed`,
                  cls: "bg-rose-950/80 text-rose-300 border-rose-800",
                }
              : { label: "All pass", cls: "bg-emerald-950/80 text-emerald-300 border-emerald-800" }}

        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
          <button
            type="button"
            class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-800/30"
            onclick={() => toggleDomain(domain.key)}
          >
            <div class="flex items-center gap-3">
              <Footprints class="h-4 w-4 text-amber-400" />
              <h3 class="text-sm font-bold text-slate-50">{domain.label}</h3>
              <span
                class="inline-block rounded-full border px-2.5 py-0.5 text-caption font-semibold {eBadge.cls}"
                >{eBadge.label}</span
              >
            </div>
            {#if isOpen}<ChevronDown class="h-4 w-4 text-slate-400" />{:else}<ChevronRight
                class="h-4 w-4 text-slate-400"
              />{/if}
          </button>

          {#if isOpen}
            <div class="space-y-4 px-4 pb-5">
              <!-- Exit Count table -->
              {#if exitResults.length}
                {@const ePass = exitResults.filter((r: ExitCountResult) => r.passes).length}
                <div>
                  <button
                    type="button"
                    class="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-300"
                    onclick={() => toggleSection("exit-count")}
                  >
                    {#if openSections["exit-count"]}<ChevronDown
                        class="h-3.5 w-3.5"
                      />{:else}<ChevronRight class="h-3.5 w-3.5" />{/if}
                    Exit Count ({exitData.total_exterior_doors || 0} exterior door(s))
                    <span class="font-mono text-micro text-slate-500"
                      >{ePass}/{exitResults.length} pass</span
                    >
                  </button>
                  {#if openSections["exit-count"]}
                    <div class="overflow-auto rounded-lg border border-slate-800">
                      <table class="w-full text-xs">
                        <thead
                          ><tr class="bg-slate-800/80">
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                              >Storey</th
                            >
                            <th class="px-3 py-2 text-center text-xs font-semibold text-slate-400"
                              >Exits</th
                            >
                            <th class="px-3 py-2 text-center text-xs font-semibold text-slate-400"
                              >Required</th
                            >
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                              >Status</th
                            >
                          </tr></thead
                        >
                        <tbody>
                          {#each exitResults as r (r)}
                            <tr class="border-b border-slate-800/60 last:border-0">
                              <td class="px-3 py-2 text-xs text-slate-50">{r.storey}</td>
                              <td class="px-3 py-2 text-center font-mono text-xs text-slate-300"
                                >{r.exit_count}</td
                              >
                              <td class="px-3 py-2 text-center font-mono text-xs text-slate-300"
                                >{r.required_min}</td
                              >
                              <td
                                class="px-3 py-2 text-xs font-semibold {r.passes
                                  ? 'text-emerald-400'
                                  : 'text-rose-400'}">{r.passes ? "✓ Pass" : "✗ Fail"}</td
                              >
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  {/if}
                </div>
              {:else}
                <p class="text-xs text-amber-400">
                  No exterior doors found. Tag doors as IsExternal=True in your authoring tool.
                </p>
              {/if}

              <!-- Travel Distance table -->
              {#if travel.length}
                {@const tdPass = travel.filter((r: TravelDistanceResult) => r.passes).length}
                <div>
                  <button
                    type="button"
                    class="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-300"
                    onclick={() => toggleSection("travel-dist")}
                  >
                    {#if openSections["travel-dist"]}<ChevronDown
                        class="h-3.5 w-3.5"
                      />{:else}<ChevronRight class="h-3.5 w-3.5" />{/if}
                    Travel Distance
                    <span class="font-mono text-micro text-slate-500"
                      >{tdPass}/{travel.length} pass</span
                    >
                  </button>
                  {#if openSections["travel-dist"]}
                    <div class="max-h-64 overflow-auto rounded-lg border border-slate-800">
                      <table class="w-full text-xs">
                        <thead
                          ><tr class="bg-slate-800/80">
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                              >Floor</th
                            >
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                              >Room</th
                            >
                            <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400"
                              >Distance</th
                            >
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                              >Nearest Exit</th
                            >
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                              >Status</th
                            >
                          </tr></thead
                        >
                        <tbody>
                          {#each [...travel].sort( (a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1) ) as r (r)}
                            <tr class="border-b border-slate-800/60 last:border-0">
                              <td class="px-3 py-2 text-xs text-slate-400"
                                >{r.storey_name || "—"}</td
                              >
                              <td class="px-3 py-2 text-xs text-slate-50"
                                >{(r.space_name || "").slice(0, 35)}</td
                              >
                              <td class="px-3 py-2 text-right font-mono text-xs text-slate-300">
                                {r.travel_distance_m !== null && r.travel_distance_m !== undefined
                                  ? `${r.travel_distance_m.toFixed(1)} m`
                                  : "No path"}
                              </td>
                              <td class="px-3 py-2 text-xs text-slate-300"
                                >{r.nearest_exit || "—"}</td
                              >
                              <td
                                class="px-3 py-2 text-xs font-semibold {r.passes
                                  ? 'text-emerald-400'
                                  : 'text-rose-400'}"
                              >
                                {r.passes ? "✓ Pass" : r.no_path ? "✗ No path" : "✗ Exceeds"}
                              </td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {:else if domain.key === "plumbing"}
        <!-- Plumbing fixture counts (inventory only) -->
        {@const fc = buildingSummary?.fixture_counts || {}}
        {@const pBadge = Object.keys(fc).length
          ? { label: "Inventory only", cls: "bg-blue-950/80 text-blue-300 border-blue-800" }
          : {
              label: "N/A — no fixtures found",
              cls: "bg-slate-800 text-slate-400 border-slate-700",
            }}

        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
          <button
            type="button"
            class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-800/30"
            onclick={() => toggleDomain(domain.key)}
          >
            <div class="flex items-center gap-3">
              <Droplets class="h-4 w-4 text-cyan-400" />
              <h3 class="text-sm font-bold text-slate-50">{domain.label}</h3>
              <span
                class="inline-block rounded-full border px-2.5 py-0.5 text-caption font-semibold {pBadge.cls}"
                >{pBadge.label}</span
              >
            </div>
            {#if isOpen}<ChevronDown class="h-4 w-4 text-slate-400" />{:else}<ChevronRight
                class="h-4 w-4 text-slate-400"
              />{/if}
          </button>
          {#if isOpen && Object.keys(fc).length}
            <div class="px-4 pb-5">
              <div class="flex flex-wrap gap-2">
                {#each Object.entries(fc).sort() as [k, v] (k)}
                  <span
                    class="inline-block rounded-full border border-cyan-800/60 bg-cyan-950/60 px-2.5 py-1 text-xs font-medium text-cyan-300"
                    >{k}: {v}</span
                  >
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {:else if domain.key === "garage"}
        <!-- Garage / Carport -->
        {@const garageSep = (result.spatial_checks || {}).garage_separation || {}}
        {@const gResults = garageSep.results || []}
        {@const gWarnings = garageSep.warnings || []}
        {@const gFail = gResults.filter((r: GarageResult) => !r.passes).length}
        {@const gBadge =
          !gResults.length && !gWarnings.length
            ? {
                label: "N/A — no garage detected",
                cls: "bg-slate-800 text-slate-400 border-slate-700",
              }
            : gFail > 0
              ? {
                  label: `${gFail} separation issue(s)`,
                  cls: "bg-rose-950/80 text-rose-300 border-rose-800",
                }
              : { label: "All pass", cls: "bg-emerald-950/80 text-emerald-300 border-emerald-800" }}

        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
          <button
            type="button"
            class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-800/30"
            onclick={() => toggleDomain(domain.key)}
          >
            <div class="flex items-center gap-3">
              <Car class="h-4 w-4 text-slate-300" />
              <h3 class="text-sm font-bold text-slate-50">{domain.label}</h3>
              <span
                class="inline-block rounded-full border px-2.5 py-0.5 text-caption font-semibold {gBadge.cls}"
                >{gBadge.label}</span
              >
            </div>
            {#if isOpen}<ChevronDown class="h-4 w-4 text-slate-400" />{:else}<ChevronRight
                class="h-4 w-4 text-slate-400"
              />{/if}
          </button>
          {#if isOpen && gResults.length}
            <div class="px-4 pb-5">
              <div class="max-h-64 overflow-auto rounded-lg border border-slate-800">
                <table class="w-full text-xs">
                  <thead
                    ><tr class="bg-slate-800/80">
                      <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Type</th>
                      <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                        >Element</th
                      >
                      <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                        >Garage Space</th
                      >
                      <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                        >Adjacent</th
                      >
                      <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                        >Rating</th
                      >
                      <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                        >Required</th
                      >
                      <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                        >Status</th
                      >
                    </tr></thead
                  >
                  <tbody>
                    {#each [...gResults].sort( (a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1) ) as r (r)}
                      <tr class="border-b border-slate-800/60 last:border-0">
                        <td class="px-3 py-2 text-xs font-semibold text-slate-50"
                          >{r.element_type}</td
                        >
                        <td class="px-3 py-2 font-mono text-xs text-slate-300"
                          >{(r.element_name || "").slice(0, 35)}</td
                        >
                        <td class="px-3 py-2 text-xs text-slate-300"
                          >{(r.garage_space || "").slice(0, 25)}</td
                        >
                        <td class="px-3 py-2 text-xs text-slate-300"
                          >{(r.adjacent_space || "").slice(0, 25)}</td
                        >
                        <td
                          class="px-3 py-2 font-mono text-xs {r.missing_rating
                            ? 'text-rose-400'
                            : r.passes
                              ? 'text-emerald-400'
                              : 'text-amber-400'}"
                        >
                          {r.fire_rating_raw || "⚠ Not declared"}
                        </td>
                        <td class="px-3 py-2 font-mono text-xs text-slate-400"
                          >≥ {r.required_min} min</td
                        >
                        <td
                          class="px-3 py-2 text-xs font-semibold {r.passes
                            ? 'text-emerald-400'
                            : 'text-rose-400'}">{r.passes ? "✓ Pass" : "✗ Fail"}</td
                        >
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </div>
          {/if}
        </div>
      {:else}
        <!-- Standard domain card (windows, doors, stairs, ramps, washrooms, fire) -->
        {@const activeRules = rules.filter((r) => r.status !== "NO_ELEMENTS")}
        {@const domIcon =
          domain.key === "windows"
            ? Wind
            : domain.key === "doors"
              ? DoorOpen
              : domain.key === "fire"
                ? Flame
                : Layers}

        {@const SvelteComponent = domIcon}
        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
          <button
            type="button"
            class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-800/30"
            onclick={() => toggleDomain(domain.key)}
          >
            <div class="flex items-center gap-3">
              <SvelteComponent
                class="h-4 w-4 {domain.key === 'fire'
                  ? 'text-rose-400'
                  : domain.key === 'windows'
                    ? 'text-cyan-400'
                    : 'text-slate-300'}"
              />
              <h3 class="text-sm font-bold text-slate-50">{domain.label}</h3>
              <span
                class="inline-block rounded-full border px-2.5 py-0.5 text-caption font-semibold {badge.cls}"
                >{badge.label}</span
              >
            </div>
            {#if isOpen}<ChevronDown class="h-4 w-4 text-slate-400" />{:else}<ChevronRight
                class="h-4 w-4 text-slate-400"
              />{/if}
          </button>

          {#if isOpen}
            <div class="space-y-4 px-4 pb-5">
              <!-- Daylight ratio sub-section for windows -->
              {#if domain.key === "windows"}
                {@const daylight = (result.spatial_checks || {}).daylight || []}
                {#if daylight.length}
                  {@const dPass = daylight.filter((r: DaylightResult) => r.passes).length}
                  {@const dFail = daylight.length - dPass}
                  <div>
                    <button
                      type="button"
                      class="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-300"
                      onclick={() => toggleSection("daylight")}
                    >
                      {#if openSections["daylight"]}<ChevronDown
                          class="h-3.5 w-3.5"
                        />{:else}<ChevronRight class="h-3.5 w-3.5" />{/if}
                      Daylight Ratio
                      <span class="font-mono text-micro text-slate-500"
                        >{dPass}/{daylight.length} pass</span
                      >
                    </button>
                    {#if openSections["daylight"] || dFail > 0}
                      <div class="max-h-64 overflow-auto rounded-lg border border-slate-800">
                        <table class="w-full text-xs">
                          <thead
                            ><tr class="bg-slate-800/80">
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Floor</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Room</th
                              >
                              <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400"
                                >Floor m²</th
                              >
                              <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400"
                                >Window m²</th
                              >
                              <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400"
                                >Ratio</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Status</th
                              >
                            </tr></thead
                          >
                          <tbody>
                            {#each [...daylight].sort( (a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1) ) as r (r)}
                              <tr class="border-b border-slate-800/60 last:border-0">
                                <td class="px-3 py-2 text-xs text-slate-400"
                                  >{r.storey_name || "—"}</td
                                >
                                <td class="px-3 py-2 text-xs text-slate-50"
                                  >{(r.space_name || "").slice(0, 35)}</td
                                >
                                <td class="px-3 py-2 text-right font-mono text-xs text-slate-300"
                                  >{r.floor_area_m2.toFixed(1)}</td
                                >
                                <td class="px-3 py-2 text-right font-mono text-xs text-slate-300"
                                  >{r.total_window_area_m2.toFixed(2)}</td
                                >
                                <td class="px-3 py-2 text-right font-mono text-xs text-slate-300"
                                  >{r.daylight_ratio.toFixed(3)}</td
                                >
                                <td
                                  class="px-3 py-2 text-xs font-semibold {r.passes
                                    ? 'text-emerald-400'
                                    : 'text-rose-400'}">{r.passes ? "✓ Pass" : "✗ Fail"}</td
                                >
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      </div>
                    {/if}
                  </div>
                {/if}
              {/if}

              <!-- Fire separation sub-section -->
              {#if domain.key === "fire"}
                {@const fireSep = (result.spatial_checks || {}).fire_separation || []}
                {#if fireSep.length}
                  {@const fPass = fireSep.filter((r: FireSeparationResult) => r.passes).length}
                  {@const fFail = fireSep.length - fPass}
                  <div>
                    <button
                      type="button"
                      class="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-300"
                      onclick={() => toggleSection("fire-sep")}
                    >
                      {#if openSections["fire-sep"]}<ChevronDown
                          class="h-3.5 w-3.5"
                        />{:else}<ChevronRight class="h-3.5 w-3.5" />{/if}
                      Fire Separation
                      <span class="font-mono text-micro text-slate-500"
                        >{fPass}/{fireSep.length} pass</span
                      >
                    </button>
                    {#if openSections["fire-sep"] || fFail > 0}
                      <div class="max-h-64 overflow-auto rounded-lg border border-slate-800">
                        <table class="w-full text-xs">
                          <thead
                            ><tr class="bg-slate-800/80">
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Wall</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Between Spaces</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Fire Rating</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Status</th
                              >
                            </tr></thead
                          >
                          <tbody>
                            {#each [...fireSep].sort( (a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1) ) as r (r)}
                              {@const spaces =
                                (r.adjacent_spaces || []).slice(0, 2).join(", ") +
                                (r.adjacent_spaces?.length > 2
                                  ? ` +${r.adjacent_spaces.length - 2}`
                                  : "")}
                              <tr class="border-b border-slate-800/60 last:border-0">
                                <td class="px-3 py-2 font-mono text-xs text-slate-50"
                                  >{(r.wall_name || "").slice(0, 35)}</td
                                >
                                <td class="px-3 py-2 text-xs text-slate-300"
                                  >{spaces.slice(0, 50)}</td
                                >
                                <td
                                  class="px-3 py-2 font-mono text-xs {r.missing_rating
                                    ? 'text-rose-400'
                                    : r.passes
                                      ? 'text-emerald-400'
                                      : 'text-amber-400'}"
                                >
                                  {r.fire_rating_raw || "⚠ Not declared"}
                                </td>
                                <td
                                  class="px-3 py-2 text-xs font-semibold {r.passes
                                    ? 'text-emerald-400'
                                    : 'text-rose-400'}">{r.passes ? "✓ Pass" : "✗ Fail"}</td
                                >
                              </tr>
                            {/each}
                          </tbody>
                        </table>
                      </div>
                    {/if}
                  </div>
                {/if}

                <!-- Alarm inventory -->
                {#if buildingSummary?.alarm_counts && Object.keys(buildingSummary.alarm_counts).length}
                  <div>
                    <button
                      type="button"
                      class="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-300"
                      onclick={() => toggleSection("alarms")}
                    >
                      {#if openSections["alarms"]}<ChevronDown
                          class="h-3.5 w-3.5"
                        />{:else}<ChevronRight class="h-3.5 w-3.5" />{/if}
                      Alarm Inventory
                      <span class="font-mono text-micro text-slate-500"
                        >{Object.values(buildingSummary.alarm_counts).reduce((a, b) => a + b, 0)} alarms</span
                      >
                    </button>
                    {#if openSections["alarms"]}
                      <div class="flex flex-wrap gap-2">
                        {#each Object.entries(buildingSummary.alarm_counts).sort() as [k, v] (k)}
                          <span
                            class="inline-block rounded-full border border-rose-800/60 bg-rose-950/60 px-2.5 py-1 text-xs font-medium text-rose-300"
                            >{k}: {v}</span
                          >
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}
              {/if}

              <!-- Per-rule collapsible sections -->
              {#if activeRules.length === 0}
                <p class="text-xs italic text-slate-500">
                  No applicable checks found in the rule library for this category.
                </p>
              {:else}
                {#each activeRules as rule (rule)}
                  {@const rKey = `${domain.key}-${rule.rule_ref || rule.property_name}`}
                  {@const rStatus = rule.status || ""}
                  {@const failC = rule.fail_count || 0}
                  {@const passC = rule.pass_count || 0}
                  {@const missC = rule.missing_count || 0}
                  {@const totalC = rule.total_count || 0}
                  {@const summaryTxt =
                    failC || missC
                      ? `${failC} fail · ${passC} pass · ${missC} missing`
                      : `${passC}/${totalC} pass`}
                  {@const ruleLabel = `${rule.rule_ref || ""}  ${(rule.rule_desc || "").slice(0, 65)}`}
                  {@const isRuleOpen =
                    openRules[rKey] || rStatus === "FAIL" || rStatus === "MISSING_DATA"}

                  <div class="overflow-hidden rounded-xl border border-slate-800/60">
                    <button
                      type="button"
                      class="flex w-full items-center justify-between px-3.5 py-2.5 text-left transition-colors hover:bg-slate-800/30"
                      onclick={() => toggleRule(rKey)}
                    >
                      <div class="flex min-w-0 items-center gap-2">
                        {#if isRuleOpen}<ChevronDown
                            class="h-3.5 w-3.5 shrink-0 text-slate-400"
                          />{:else}<ChevronRight class="h-3.5 w-3.5 shrink-0 text-slate-400" />{/if}
                        <span class="truncate text-xs font-medium text-slate-200">{ruleLabel}</span>
                      </div>
                      <span class="ml-2 shrink-0 font-mono text-micro text-slate-400"
                        >{summaryTxt} · {ruleRequiredText(rule)}</span
                      >
                    </button>

                    {#if isRuleOpen}
                      {@const sortedEls = [...(rule.all_elements || [])].sort(
                        (a: RuleElementResult, b: RuleElementResult) => {
                          const order: Record<string, number> = { FAIL: 0, MISSING: 1, PASS: 2 };
                          return (order[a.status ?? ""] ?? 3) - (order[b.status ?? ""] ?? 3);
                        },
                      )}
                      {#if rule.property_name}
                        <div
                          class="flex items-center gap-1.5 border-t border-slate-800/60 px-3.5 py-1.5 text-micro text-slate-500"
                        >
                          Checks
                          <BsddBadge kind="property" value={rule.property_name} class="font-mono text-slate-300" />
                        </div>
                      {/if}
                      <div class="max-h-64 overflow-auto border-t border-slate-800/60">
                        <table class="w-full text-xs">
                          <thead
                            ><tr class="bg-slate-800/80">
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Element</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Floor / Room</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >GUID</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Actual</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Required</th
                              >
                              <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400"
                                >Status</th
                              >
                            </tr></thead
                          >
                          <tbody>
                            {#each sortedEls.slice(0, 50) as el (el.guid)}
                              {@const elStatus = el.status || ""}
                              {@const actualTxt =
                                fmtVal(el.actual) +
                                (rule.unit && el.actual != null ? ` ${rule.unit}` : "")}
                              {@const statusTxt =
                                elStatus === "FAIL"
                                  ? el.reason || "fail"
                                  : elStatus === "MISSING"
                                    ? "missing"
                                    : "✓ pass"}
                              {@const statusCls =
                                elStatus === "FAIL"
                                  ? "text-rose-400 font-semibold"
                                  : elStatus === "MISSING"
                                    ? "text-amber-400 font-semibold"
                                    : "text-emerald-400"}
                              {@const rowBg =
                                elStatus === "FAIL"
                                  ? "bg-rose-950/20"
                                  : elStatus === "MISSING"
                                    ? "bg-amber-950/20"
                                    : ""}
                              <tr class="border-b border-slate-800/40 last:border-0 {rowBg}">
                                <td class="px-3 py-2">
                                  <span class="font-mono text-xs text-slate-50"
                                    >{(el.element_name || "—").slice(0, 32)}</span
                                  >
                                </td>
                                <td class="px-3 py-2">
                                  <span class="block text-xs text-slate-300"
                                    >{el.storey || "—"}</span
                                  >
                                  {#if el.space && el.space !== "—"}
                                    <span class="block text-xs text-slate-500">{el.space}</span>
                                  {/if}
                                </td>
                                <td class="px-3 py-2"
                                  ><span class="font-mono text-xs text-slate-500"
                                    >{(el.guid || "").slice(0, 14)}</span
                                  ></td
                                >
                                <td
                                  class="px-3 py-2 font-mono text-xs text-slate-300 {elStatus ===
                                  'FAIL'
                                    ? 'font-semibold text-rose-300'
                                    : elStatus === 'MISSING'
                                      ? 'font-semibold text-amber-300'
                                      : ''}">{actualTxt}</td
                                >
                                <td class="px-3 py-2 text-xs text-slate-500"
                                  >{ruleRequiredText(rule)}</td
                                >
                                <td class="px-3 py-2 text-xs {statusCls}">
                                  {statusTxt}
                                  {#if elStatus === "FAIL" && el.guid && selectedProjectId}
                                    <button
                                      type="button"
                                      class="ml-2 text-blue-400 hover:text-blue-300 hover:underline"
                                      onclick={stopPropagation(() =>
                                        openViewerInNewTab(
                                          selectedProjectId!,
                                          el.guid,
                                          result?.bcf_artifact_id || undefined,
                                        ),
                                      )}>View in 3D</button
                                    >
                                  {/if}
                                </td>
                              </tr>
                            {/each}
                            {#if sortedEls.length > 50}
                              <tr
                                ><td colspan="6" class="px-3 py-2 text-xs italic text-slate-500"
                                  >… and {sortedEls.length - 50} more</td
                                ></tr
                              >
                            {/if}
                          </tbody>
                        </table>
                      </div>
                    {/if}
                  </div>
                {/each}
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    {/each}
  {:else if isRunning}
    <div class="space-y-2 p-16 text-center text-xs text-slate-400">
      <div
        class="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent"
      ></div>
      <p>
        {#if selectedFolder}
          Running "{selectedFolderDisplayName}" ruleset compliance analysis…
        {:else}
          Running Ontario Building Code architectural compliance analysis…
        {/if}
      </p>
    </div>
  {:else}
    <div
      class="rounded-2xl border border-dashed border-slate-800 p-16 text-center text-xs text-slate-500"
    >
      Select a project and click "Run ARCH Audit" to inspect building code compliance.
    </div>
  {/if}
</div>

<!-- Quality Improvements modal (shown when no enhanced model exists) -->
<ProjectEnhancementsModal
  isOpen={showEnhancementsModal}
  project={selectedProject}
  onClose={handleEnhancementsModalClose}
/>
