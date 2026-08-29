<script lang="ts">
  import { onMount } from 'svelte';
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
  } from 'lucide-svelte';
  import { projectsApi, analyzeApi, lineageApi, rulesApi } from '../lib/api';
  import ProjectEnhancementsModal from '../lib/components/ProjectEnhancementsModal.svelte';
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
  } from '../lib/types';

  export let initialProjectId: number | null = null;
  export let onSelectProjectForViewer: (projectId: number, elementGuid?: string, bcfArtifactId?: number) => void;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let isRunning = false;
  let error = '';
  let result: ArchAnalysisResult | null = null;

  // Rule folder selection — '' means "All rules"
  let ruleFolders: RuleFolder[] = [];
  let selectedFolder = ''; // '' = All
  let isFoldersLoading = false;

  // Enhanced model gate
  let hasEnhancedModel: boolean | null = null;
  let isCheckingEnhancement = false;
  let showEnhancementsModal = false;

  // BCF save tracking (backend auto-persists; we reflect the status)
  let bcfSaveMessage = '';
  let bcfSaveType: 'success' | 'error' = 'success';

  $: selectedProject = projects.find((p) => p.id === selectedProjectId) || null;

  // Collapsible state tracking
  let openDomains: Record<string, boolean> = {};
  let openRules: Record<string, boolean> = {};
  let openSections: Record<string, boolean> = {};

  onMount(async () => {
    // Load projects and rule folders in parallel; do NOT auto-run analysis
    try {
      const [projectData] = await Promise.all([
        projectsApi.list(),
        loadFolders(),
      ]);
      projects = projectData.projects || [];
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
      // Only check for enhanced model — do not auto-run
      if (selectedProjectId) {
        await checkEnhancedModel();
      }
    } catch (err: any) {
      error = err.message || 'Failed to load projects';
    }
  });

  async function loadFolders(): Promise<void> {
    isFoldersLoading = true;
    try {
      ruleFolders = await rulesApi.folders('Arch');
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
    error = '';
    bcfSaveMessage = '';
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

  async function runCheck() {
    if (!selectedProjectId) return;
    isRunning = true;
    error = '';
    bcfSaveMessage = '';
    try {
      result = await analyzeApi.runArch(selectedProjectId, selectedFolder);
      if (result) {
        initDomainState(result);
        if (result.bcf_artifact_id) {
          bcfSaveMessage = `BCF report saved to database (artifact #${result.bcf_artifact_id})`;
          bcfSaveType = 'success';
        } else if (result.total_issues > 0) {
          bcfSaveMessage = 'BCF report auto-persistence encountered an issue.';
          bcfSaveType = 'error';
        }
      }
    } catch (err: any) {
      error = err.message || 'Architectural compliance check failed.';
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
    if (seconds === undefined || seconds === null) return '';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);
    return `${minutes}m ${rest}s`;
  }

  function fmtVal(v: any): string {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') {
      return v >= 1 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v.toFixed(4);
    }
    return String(v);
  }

  function ruleRequiredText(rule: RuleComplianceResult): string {
    const op = rule.operator || '';
    const cv = rule.check_value;
    const unit = rule.unit || '';
    if (op === '>=') return `≥ ${cv} ${unit}`.trim();
    if (op === '<=') return `≤ ${cv} ${unit}`.trim();
    if (op === 'between') return `${rule.value_min}–${rule.value_max} ${unit}`.trim();
    if (op === 'exists') return 'must be present';
    if (op === 'not_exists') return 'must not be present';
    return cv !== null && cv !== undefined ? `${op} ${cv} ${unit}`.trim() : '—';
  }

  const ELEM_LABELS: Record<string, string> = {
    IfcDoor: 'Doors',
    IfcWindow: 'Windows',
    IfcStairFlight: 'Stair Flights',
    IfcRailing: 'Railings',
    IfcRamp: 'Ramps',
    IfcRampFlight: 'Ramp Flights',
    IfcSanitaryTerminal: 'Sanitary Terminals',
    IfcAlarm: 'Alarms',
    IfcWall: 'Walls',
    IfcSlab: 'Slabs',
    IfcSpace: 'Spaces',
    IfcBuildingStorey: 'Storeys',
  };

  // Category → IFC target classes (matching the legacy _SIMPLE_CATEGORY_TARGETS)
  const DOMAIN_TARGETS: Record<string, string[]> = {
    windows: ['IfcWindow'],
    doors: ['IfcDoor'],
    stairs: ['IfcStairFlight', 'IfcRailing'],
    ramps: ['IfcRamp', 'IfcRampFlight'],
    washrooms: ['IfcSanitaryTerminal'],
    fire: ['IfcAlarm'],
  };

  interface DomainConfig {
    key: string;
    label: string;
    targets: string[];
    category: string;
  }

  const DOMAIN_CARDS: DomainConfig[] = [
    { key: 'windows', label: 'Windows & Glazing', targets: ['IfcWindow'], category: 'windows' },
    { key: 'doors', label: 'Doors', targets: ['IfcDoor'], category: 'doors' },
    { key: 'stairs', label: 'Stairs, Guards & Handrails', targets: ['IfcStairFlight', 'IfcRailing'], category: 'stairs' },
    { key: 'ramps', label: 'Ramps', targets: ['IfcRamp', 'IfcRampFlight'], category: 'ramps' },
    { key: 'egress', label: 'Means of Egress', targets: [], category: 'egress' },
    { key: 'washrooms', label: 'Washrooms & Accessibility', targets: ['IfcSanitaryTerminal'], category: 'washrooms' },
    { key: 'plumbing', label: 'Plumbing Fixture Counts', targets: [], category: 'plumbing' },
    { key: 'fire', label: 'Fire Protection (House-Level)', targets: ['IfcAlarm'], category: 'fire' },
    { key: 'garage', label: 'Garage / Carport', targets: [], category: 'garage' },
  ];

  function getDomainRules(targets: string[]): RuleComplianceResult[] {
    if (!result?.rule_compliance) return [];
    return result.rule_compliance.filter((r) => targets.includes(r.target || ''));
  }

  function domainBadge(rules: RuleComplianceResult[]): { label: string; cls: string } {
    if (!rules.length) return { label: 'N/A', cls: 'bg-slate-800 text-slate-400 border-slate-700' };
    const real = rules.filter((r) => r.status !== 'NO_ELEMENTS');
    if (!real.length) return { label: 'N/A', cls: 'bg-slate-800 text-slate-400 border-slate-700' };
    const nFail = real.filter((r) => r.status === 'FAIL').length;
    if (nFail) return { label: `${nFail} rule(s) failed`, cls: 'bg-rose-950/80 text-rose-300 border-rose-800' };
    if (real.some((r) => ['MISSING_DATA', 'PARTIAL'].includes(r.status || '')))
      return { label: 'Missing data', cls: 'bg-amber-950/80 text-amber-300 border-amber-800' };
    return { label: 'All pass', cls: 'bg-emerald-950/80 text-emerald-300 border-emerald-800' };
  }

  function initDomainState(r: ArchAnalysisResult) {
    const rc = r.rule_compliance || [];
    for (const dc of DOMAIN_CARDS) {
      const rules = rc.filter((rule) => dc.targets.includes(rule.target || ''));
      const hasFail = rules.some((rule) => rule.status === 'FAIL');
      openDomains[dc.key] = hasFail;
    }
    // Egress / fire / garage open if they have failures
    const eg = r.egress_checks || {};
    const exitResults = eg.exit_count?.results || [];
    const travel = eg.travel_distance || [];
    if ([...exitResults, ...travel].some((x: any) => !x.passes)) openDomains['egress'] = true;
    const fireSep = (r.spatial_checks || {}).fire_separation || [];
    if (fireSep.some((x: any) => !x.passes)) openDomains['fire'] = true;
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

  // ── Reactive derivations ────────────────────────────────────────────────

  $: summary = result?.rule_compliance_summary || {};
  $: passRate = summary.pass_rate !== undefined ? Number(summary.pass_rate) : null;
  $: durationSeconds = summary.duration_seconds;
  $: uniqueElements = summary.unique_elements_evaluated || 0;
  $: rulesWithElements = summary.rules_with_elements || 0;
  $: totalRules = summary.total_rules || 0;
  $: buildingSummary = result?.building_summary;
  $: folderNote = result?.rule_folder ? ` · ${result.rule_folder}` : (selectedFolder ? ` · ${selectedFolder}` : '');
</script>

<div class="space-y-5 max-w-7xl mx-auto">
  <!-- ═══ Header ═══ -->
  <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Analysis</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        {#if result}
          {result.project_name} — ARCH Analysis{folderNote}
        {:else}
          Architectural Compliance Audit
        {/if}
      </h1>
      <p class="text-xs sm:text-sm text-slate-400 mt-1">
        Domain-based compliance check against Ontario Building Code Part 9.
      </p>

      <!-- Pass rate pill + coverage evidence -->
      {#if result && totalRules > 0}
        <div class="flex flex-wrap items-center gap-3 mt-3">
          {#if passRate !== null}
            <span
              class="inline-block px-3 py-1 rounded-full text-xs font-bold tracking-wide border {passRate >= 80
                ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800'
                : passRate >= 50
                  ? 'bg-amber-950/80 text-amber-300 border-amber-800'
                  : 'bg-rose-950/80 text-rose-300 border-rose-800'}"
            >
              {passRate.toFixed(0)}% pass rate
            </span>
          {/if}
          {#if durationSeconds !== undefined && durationSeconds !== null}
            <span class="inline-flex items-center gap-1 text-xs text-slate-400 font-mono">
              <Timer class="w-3.5 h-3.5 text-blue-400" />
              ⏱ {formatDuration(durationSeconds)}
            </span>
          {/if}
          {#if uniqueElements > 0}
            <span class="text-xs text-slate-400">
              🔍 <strong class="text-slate-300">{uniqueElements}</strong> element(s) checked across
              <strong class="text-slate-300">{rulesWithElements}</strong> applicable rule(s) — every match evaluated, no sampling
            </span>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Project selector & Run button -->
    <div class="flex items-center gap-2.5 flex-wrap shrink-0">
      <select
        bind:value={selectedProjectId}
        on:change={handleProjectChange}
        class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
      >
        {#each projects as project}
          <option value={project.id}>{project.name}</option>
        {/each}
      </select>

      {#if result && selectedProjectId}
        <button
          type="button"
          on:click={() => selectedProjectId && onSelectProjectForViewer(selectedProjectId, undefined, result?.bcf_artifact_id || undefined)}
          class="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-emerald-800/80 hover:bg-emerald-700 text-white border border-emerald-700 transition-colors"
          title="Open in 3D ThatOpen Viewer with error viewpoints"
        >
          <ScanEye class="w-3.5 h-3.5" />
          View in 3D / BCF
        </button>
        {#if result.bcf_artifact_id}
          <a
            href={analyzeApi.getBcfArtifactUrl(result.bcf_artifact_id)}
            download
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
          >
            <Download class="w-3.5 h-3.5" />
            BCF
          </a>
        {/if}
      {/if}

      <button
        type="button"
        disabled={isRunning || isCheckingEnhancement || !selectedProjectId}
        on:click={handleRunClick}
        class="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50"
      >
        <Play class="w-3.5 h-3.5" />
        {isRunning ? 'Auditing…' : isCheckingEnhancement ? 'Checking model…' : 'Run ARCH Audit'}
      </button>
    </div>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">{error}</div>
  {/if}

  {#if bcfSaveMessage}
    <div class="p-3.5 rounded-xl flex items-center gap-2 text-xs
      {bcfSaveType === 'success'
        ? 'bg-emerald-950/40 border border-emerald-800 text-emerald-300'
        : 'bg-rose-950/40 border border-rose-800 text-rose-300'}">
      <CheckCircle2 class="w-4 h-4 shrink-0 {bcfSaveType === 'success' ? 'text-emerald-400' : 'text-rose-400'}" />
      <span>{bcfSaveMessage}</span>
      {#if result?.bcf_artifact_id}
        <a
          href={analyzeApi.getBcfArtifactUrl(result.bcf_artifact_id)}
          download
          class="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-900/60 hover:bg-emerald-800 text-emerald-200 border border-emerald-700 transition-colors"
        >
          <Download class="w-3 h-3" />
          Download BCF
        </a>
      {/if}
    </div>
  {/if}

  <!-- ═══ Ruleset Folder Selector ═══ -->
  {#if hasEnhancedModel && !isCheckingEnhancement && selectedProjectId}
    <div class="p-4 rounded-2xl bg-slate-900/50 border border-slate-800 flex flex-col sm:flex-row sm:items-center gap-3">
      <div class="flex items-center gap-2 shrink-0">
        <FolderOpen class="w-4 h-4 text-blue-400" />
        <span class="text-xs font-semibold text-slate-300">Ruleset</span>
      </div>
      <div class="flex flex-wrap gap-2 flex-1">
        <!-- "All" option -->
        <button
          type="button"
          on:click={() => (selectedFolder = '')}
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all border
            {selectedFolder === ''
              ? 'bg-[#0071e3] border-blue-500 text-white shadow-sm shadow-blue-500/20'
              : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'}"
        >
          All Rules
        </button>
        {#if isFoldersLoading}
          <span class="text-xs text-slate-500 italic px-2 py-1.5">Loading folders…</span>
        {:else}
          {#each ruleFolders as folder}
            <button
              type="button"
              on:click={() => (selectedFolder = folder.ruleset_id)}
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all border
                {selectedFolder === folder.ruleset_id
                  ? 'bg-[#0071e3] border-blue-500 text-white shadow-sm shadow-blue-500/20'
                  : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white'}"
              title={folder.description || folder.display_name}
            >
              {folder.display_name}
            </button>
          {/each}
        {/if}
      </div>
      {#if selectedFolder}
        <span class="text-[10px] text-slate-500 shrink-0">Selected: <span class="text-slate-300 font-mono">{selectedFolder}</span> (scopes audit to this ruleset only)</span>
      {:else}
        <span class="text-[10px] text-slate-500 shrink-0">Scope: <span class="text-slate-300">All building code rules</span></span>
      {/if}
    </div>
  {/if}

  {#if hasEnhancedModel === false && !isCheckingEnhancement}
    <!-- No enhanced model warning banner -->
    <div class="p-4 rounded-2xl bg-purple-950/40 border border-purple-800/60 flex items-start gap-3">
      <div class="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20 shrink-0">
        <Sparkles class="w-4 h-4" />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-sm font-semibold text-purple-200">Enhanced model required</p>
        <p class="text-xs text-purple-400 mt-0.5">
          ARCH analysis runs on an enhanced/improved model. This project doesn't have one yet.
          Generate an improved model version to unlock the full compliance audit.
        </p>
      </div>
      <button
        type="button"
        on:click={() => (showEnhancementsModal = true)}
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white transition-all hover:scale-[1.02] shrink-0"
      >
        <Sparkles class="w-3.5 h-3.5" />
        Run Improvements
      </button>
    </div>
  {/if}

  {#if result}

    <!-- ═══ Building Overview card ═══ -->
    {#if buildingSummary && (buildingSummary.storey_count || buildingSummary.room_count)}
      <div class="rounded-2xl bg-slate-900/40 border border-slate-800 overflow-hidden">
        <!-- Header -->
        <button
          type="button"
          class="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/30 transition-colors"
          on:click={() => toggleSection('building')}
        >
          <h2 class="text-sm font-bold text-white flex items-center gap-2">
            <Building2 class="w-4 h-4 text-blue-400" />
            Building Overview
          </h2>
          {#if openSections['building']}
            <ChevronDown class="w-4 h-4 text-slate-400" />
          {:else}
            <ChevronRight class="w-4 h-4 text-slate-400" />
          {/if}
        </button>

        <!-- Stat strip (always visible) -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 px-4 pb-4">
          <div class="text-center px-4 py-3 bg-slate-800/60 rounded-xl">
            <span class="text-2xl font-bold text-white block">{buildingSummary.storey_count || 0}</span>
            <span class="text-xs text-slate-400">Storeys</span>
          </div>
          <div class="text-center px-4 py-3 bg-slate-800/60 rounded-xl">
            <span class="text-2xl font-bold text-white block">{buildingSummary.room_count || 0}</span>
            <span class="text-xs text-slate-400">Rooms / Spaces</span>
          </div>
          <div class="text-center px-4 py-3 bg-slate-800/60 rounded-xl">
            <span class="text-2xl font-bold text-white block">
              {buildingSummary.total_gfa_m2 ? buildingSummary.total_gfa_m2.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
            </span>
            <span class="text-xs text-slate-400">GFA m²</span>
          </div>
          <div class="text-center px-4 py-3 bg-slate-800/60 rounded-xl">
            <span class="text-2xl font-bold text-white block">{buildingSummary.external_door_count || 0}</span>
            <span class="text-xs text-slate-400">Exit Doors</span>
          </div>
        </div>

        {#if openSections['building']}
          <div class="px-4 pb-5 space-y-4">
            <!-- Floor breakdown table -->
            {#if buildingSummary.storeys && buildingSummary.storeys.length}
              {@const floorHeightMap = Object.fromEntries((buildingSummary.floor_heights || []).map((h) => [h.from, h.height_mm]))}
              <div>
                <h3 class="text-xs font-semibold text-slate-300 mb-2">Floor Breakdown</h3>
                <div class="overflow-auto border border-slate-800 rounded-lg max-h-64">
                  <table class="w-full text-xs">
                    <thead>
                      <tr class="bg-slate-800/80">
                        <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Storey</th>
                        <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Floor-to-Floor</th>
                        <th class="px-3 py-2 text-center text-xs font-semibold text-slate-400">Rooms</th>
                        <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400">Area m²</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each buildingSummary.storeys as s}
                        {@const ri = buildingSummary.rooms_per_storey?.[s.name]}
                        {@const hMm = floorHeightMap[s.name]}
                        <tr class="border-b border-slate-800/60 last:border-0">
                          <td class="px-3 py-2 text-xs font-medium text-white">{s.name}</td>
                          <td class="px-3 py-2 text-xs font-mono text-slate-300">
                            {#if hMm}
                              {hMm >= 1000 ? `${(hMm / 1000).toFixed(2)} m` : `${hMm.toLocaleString()} mm`}
                            {:else}—{/if}
                          </td>
                          <td class="px-3 py-2 text-xs text-center text-slate-300">{ri?.count || '—'}</td>
                          <td class="px-3 py-2 text-xs font-mono text-right text-slate-300">
                            {ri?.total_area_m2 ? ri.total_area_m2.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
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
                <h3 class="text-xs font-semibold text-slate-300 mb-2">Elements Found</h3>
                <div class="flex flex-wrap gap-2">
                  {#each Object.entries(buildingSummary.element_counts).sort(([a], [b]) => (ELEM_LABELS[a] || a).localeCompare(ELEM_LABELS[b] || b)) as [k, v]}
                    <span class="inline-block px-2.5 py-1 rounded-full text-xs bg-blue-950/60 text-blue-300 border border-blue-800/60 font-medium">
                      {ELEM_LABELS[k] || k}: {v}
                    </span>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Fixture count badges -->
            {#if buildingSummary.fixture_counts && Object.keys(buildingSummary.fixture_counts).length}
              <div>
                <h3 class="text-xs font-semibold text-slate-300 mb-2">Plumbing Fixtures</h3>
                <div class="flex flex-wrap gap-2">
                  {#each Object.entries(buildingSummary.fixture_counts).sort() as [k, v]}
                    <span class="inline-block px-2.5 py-1 rounded-full text-xs bg-cyan-950/60 text-cyan-300 border border-cyan-800/60 font-medium">
                      {k}: {v}
                    </span>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Alarm count badges -->
            {#if buildingSummary.alarm_counts && Object.keys(buildingSummary.alarm_counts).length}
              <div>
                <h3 class="text-xs font-semibold text-slate-300 mb-2">Fire / CO Alarms</h3>
                <div class="flex flex-wrap gap-2">
                  {#each Object.entries(buildingSummary.alarm_counts).sort() as [k, v]}
                    <span class="inline-block px-2.5 py-1 rounded-full text-xs bg-rose-950/60 text-rose-300 border border-rose-800/60 font-medium">
                      {k}: {v}
                    </span>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- QA warnings -->
            {#if (buildingSummary.unplaced_rooms?.length || 0) > 0 || (buildingSummary.unnamed_elements?.length || 0) > 0}
              <div>
                <h3 class="text-xs font-semibold text-slate-300 mb-2">Model QA</h3>
                <div class="space-y-1 p-3 bg-amber-950/30 rounded-lg border border-amber-800/40">
                  {#if (buildingSummary.unplaced_rooms?.length || 0) > 0}
                    <p class="text-xs text-amber-300">⚠ {buildingSummary.unplaced_rooms?.length} unplaced room(s) — not assigned to any storey</p>
                  {/if}
                  {#each buildingSummary.unnamed_elements || [] as u}
                    <p class="text-xs text-amber-300">⚠ {u.count} {ELEM_LABELS[u.type] || u.type} element(s) missing Name property</p>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- ═══ Domain cards ═══ -->
    {#each DOMAIN_CARDS as domain}
      {@const rules = getDomainRules(domain.targets)}
      {@const badge = domainBadge(rules)}
      {@const isOpen = openDomains[domain.key] || false}

      <!-- Special handling for domains with non-rule-compliance data -->
      {#if domain.key === 'egress'}
        <!-- Egress domain card -->
        {@const exitData = result.egress_checks?.exit_count || {}}
        {@const travel = result.egress_checks?.travel_distance || []}
        {@const exitResults = exitData.results || []}
        {@const allPasses = [...exitResults, ...travel]}
        {@const eFail = allPasses.filter((x) => !x.passes).length}
        {@const eBadge = allPasses.length === 0
          ? { label: 'N/A', cls: 'bg-slate-800 text-slate-400 border-slate-700' }
          : eFail > 0
            ? { label: `${eFail} check(s) failed`, cls: 'bg-rose-950/80 text-rose-300 border-rose-800' }
            : { label: 'All pass', cls: 'bg-emerald-950/80 text-emerald-300 border-emerald-800' }}

        <div class="rounded-2xl bg-slate-900/40 border border-slate-800 overflow-hidden">
          <button
            type="button"
            class="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/30 transition-colors"
            on:click={() => toggleDomain(domain.key)}
          >
            <div class="flex items-center gap-3">
              <Footprints class="w-4 h-4 text-amber-400" />
              <h3 class="text-sm font-bold text-white">{domain.label}</h3>
              <span class="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold border {eBadge.cls}">{eBadge.label}</span>
            </div>
            {#if isOpen}<ChevronDown class="w-4 h-4 text-slate-400" />{:else}<ChevronRight class="w-4 h-4 text-slate-400" />{/if}
          </button>

          {#if isOpen}
            <div class="px-4 pb-5 space-y-4">
              <!-- Exit Count table -->
              {#if exitResults.length}
                {@const ePass = exitResults.filter((r: ExitCountResult) => r.passes).length}
                <div>
                  <button type="button" class="flex items-center gap-2 text-xs font-semibold text-slate-300 mb-2" on:click={() => toggleSection('exit-count')}>
                    {#if openSections['exit-count']}<ChevronDown class="w-3.5 h-3.5" />{:else}<ChevronRight class="w-3.5 h-3.5" />{/if}
                    Exit Count ({exitData.total_exterior_doors || 0} exterior door(s))
                    <span class="text-[10px] font-mono text-slate-500">{ePass}/{exitResults.length} pass</span>
                  </button>
                  {#if openSections['exit-count']}
                    <div class="overflow-auto border border-slate-800 rounded-lg">
                      <table class="w-full text-xs">
                        <thead><tr class="bg-slate-800/80">
                          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Storey</th>
                          <th class="px-3 py-2 text-center text-xs font-semibold text-slate-400">Exits</th>
                          <th class="px-3 py-2 text-center text-xs font-semibold text-slate-400">Required</th>
                          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Status</th>
                        </tr></thead>
                        <tbody>
                          {#each exitResults as r}
                            <tr class="border-b border-slate-800/60 last:border-0">
                              <td class="px-3 py-2 text-xs text-white">{r.storey}</td>
                              <td class="px-3 py-2 text-xs font-mono text-center text-slate-300">{r.exit_count}</td>
                              <td class="px-3 py-2 text-xs font-mono text-center text-slate-300">{r.required_min}</td>
                              <td class="px-3 py-2 text-xs font-semibold {r.passes ? 'text-emerald-400' : 'text-rose-400'}">{r.passes ? '✓ Pass' : '✗ Fail'}</td>
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    </div>
                  {/if}
                </div>
              {:else}
                <p class="text-xs text-amber-400">No exterior doors found. Tag doors as IsExternal=True in your authoring tool.</p>
              {/if}

              <!-- Travel Distance table -->
              {#if travel.length}
                {@const tdPass = travel.filter((r: TravelDistanceResult) => r.passes).length}
                <div>
                  <button type="button" class="flex items-center gap-2 text-xs font-semibold text-slate-300 mb-2" on:click={() => toggleSection('travel-dist')}>
                    {#if openSections['travel-dist']}<ChevronDown class="w-3.5 h-3.5" />{:else}<ChevronRight class="w-3.5 h-3.5" />{/if}
                    Travel Distance
                    <span class="text-[10px] font-mono text-slate-500">{tdPass}/{travel.length} pass</span>
                  </button>
                  {#if openSections['travel-dist']}
                    <div class="overflow-auto border border-slate-800 rounded-lg max-h-64">
                      <table class="w-full text-xs">
                        <thead><tr class="bg-slate-800/80">
                          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Floor</th>
                          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Room</th>
                          <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400">Distance</th>
                          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Nearest Exit</th>
                          <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Status</th>
                        </tr></thead>
                        <tbody>
                          {#each [...travel].sort((a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1)) as r}
                            <tr class="border-b border-slate-800/60 last:border-0">
                              <td class="px-3 py-2 text-xs text-slate-400">{r.storey_name || '—'}</td>
                              <td class="px-3 py-2 text-xs text-white">{(r.space_name || '').slice(0, 35)}</td>
                              <td class="px-3 py-2 text-xs font-mono text-right text-slate-300">
                                {r.travel_distance_m !== null && r.travel_distance_m !== undefined ? `${r.travel_distance_m.toFixed(1)} m` : 'No path'}
                              </td>
                              <td class="px-3 py-2 text-xs text-slate-300">{r.nearest_exit || '—'}</td>
                              <td class="px-3 py-2 text-xs font-semibold {r.passes ? 'text-emerald-400' : 'text-rose-400'}">
                                {r.passes ? '✓ Pass' : r.no_path ? '✗ No path' : '✗ Exceeds'}
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

      {:else if domain.key === 'plumbing'}
        <!-- Plumbing fixture counts (inventory only) -->
        {@const fc = buildingSummary?.fixture_counts || {}}
        {@const pBadge = Object.keys(fc).length
          ? { label: 'Inventory only', cls: 'bg-blue-950/80 text-blue-300 border-blue-800' }
          : { label: 'N/A — no fixtures found', cls: 'bg-slate-800 text-slate-400 border-slate-700' }}

        <div class="rounded-2xl bg-slate-900/40 border border-slate-800 overflow-hidden">
          <button type="button" class="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/30 transition-colors" on:click={() => toggleDomain(domain.key)}>
            <div class="flex items-center gap-3">
              <Droplets class="w-4 h-4 text-cyan-400" />
              <h3 class="text-sm font-bold text-white">{domain.label}</h3>
              <span class="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold border {pBadge.cls}">{pBadge.label}</span>
            </div>
            {#if isOpen}<ChevronDown class="w-4 h-4 text-slate-400" />{:else}<ChevronRight class="w-4 h-4 text-slate-400" />{/if}
          </button>
          {#if isOpen && Object.keys(fc).length}
            <div class="px-4 pb-5">
              <div class="flex flex-wrap gap-2">
                {#each Object.entries(fc).sort() as [k, v]}
                  <span class="inline-block px-2.5 py-1 rounded-full text-xs bg-cyan-950/60 text-cyan-300 border border-cyan-800/60 font-medium">{k}: {v}</span>
                {/each}
              </div>
            </div>
          {/if}
        </div>

      {:else if domain.key === 'garage'}
        <!-- Garage / Carport -->
        {@const garageSep = (result.spatial_checks || {}).garage_separation || {}}
        {@const gResults = garageSep.results || []}
        {@const gWarnings = garageSep.warnings || []}
        {@const gFail = gResults.filter((r: GarageResult) => !r.passes).length}
        {@const gBadge = !gResults.length && !gWarnings.length
          ? { label: 'N/A — no garage detected', cls: 'bg-slate-800 text-slate-400 border-slate-700' }
          : gFail > 0
            ? { label: `${gFail} separation issue(s)`, cls: 'bg-rose-950/80 text-rose-300 border-rose-800' }
            : { label: 'All pass', cls: 'bg-emerald-950/80 text-emerald-300 border-emerald-800' }}

        <div class="rounded-2xl bg-slate-900/40 border border-slate-800 overflow-hidden">
          <button type="button" class="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/30 transition-colors" on:click={() => toggleDomain(domain.key)}>
            <div class="flex items-center gap-3">
              <Car class="w-4 h-4 text-slate-300" />
              <h3 class="text-sm font-bold text-white">{domain.label}</h3>
              <span class="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold border {gBadge.cls}">{gBadge.label}</span>
            </div>
            {#if isOpen}<ChevronDown class="w-4 h-4 text-slate-400" />{:else}<ChevronRight class="w-4 h-4 text-slate-400" />{/if}
          </button>
          {#if isOpen && gResults.length}
            <div class="px-4 pb-5">
              <div class="overflow-auto border border-slate-800 rounded-lg max-h-64">
                <table class="w-full text-xs">
                  <thead><tr class="bg-slate-800/80">
                    <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Type</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Element</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Garage Space</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Adjacent</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Rating</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Required</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Status</th>
                  </tr></thead>
                  <tbody>
                    {#each [...gResults].sort((a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1)) as r}
                      <tr class="border-b border-slate-800/60 last:border-0">
                        <td class="px-3 py-2 text-xs font-semibold text-white">{r.element_type}</td>
                        <td class="px-3 py-2 text-xs font-mono text-slate-300">{(r.element_name || '').slice(0, 35)}</td>
                        <td class="px-3 py-2 text-xs text-slate-300">{(r.garage_space || '').slice(0, 25)}</td>
                        <td class="px-3 py-2 text-xs text-slate-300">{(r.adjacent_space || '').slice(0, 25)}</td>
                        <td class="px-3 py-2 text-xs font-mono {r.missing_rating ? 'text-rose-400' : r.passes ? 'text-emerald-400' : 'text-amber-400'}">
                          {r.fire_rating_raw || '⚠ Not declared'}
                        </td>
                        <td class="px-3 py-2 text-xs font-mono text-slate-400">≥ {r.required_min} min</td>
                        <td class="px-3 py-2 text-xs font-semibold {r.passes ? 'text-emerald-400' : 'text-rose-400'}">{r.passes ? '✓ Pass' : '✗ Fail'}</td>
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
        {@const activeRules = rules.filter((r) => r.status !== 'NO_ELEMENTS')}
        {@const domIcon = domain.key === 'windows' ? Wind : domain.key === 'doors' ? DoorOpen : domain.key === 'fire' ? Flame : Layers}

        <div class="rounded-2xl bg-slate-900/40 border border-slate-800 overflow-hidden">
          <button
            type="button"
            class="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/30 transition-colors"
            on:click={() => toggleDomain(domain.key)}
          >
            <div class="flex items-center gap-3">
              <svelte:component this={domIcon} class="w-4 h-4 {domain.key === 'fire' ? 'text-rose-400' : domain.key === 'windows' ? 'text-cyan-400' : 'text-slate-300'}" />
              <h3 class="text-sm font-bold text-white">{domain.label}</h3>
              <span class="inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold border {badge.cls}">{badge.label}</span>
            </div>
            {#if isOpen}<ChevronDown class="w-4 h-4 text-slate-400" />{:else}<ChevronRight class="w-4 h-4 text-slate-400" />{/if}
          </button>

          {#if isOpen}
            <div class="px-4 pb-5 space-y-4">
              <!-- Daylight ratio sub-section for windows -->
              {#if domain.key === 'windows'}
                {@const daylight = (result.spatial_checks || {}).daylight || []}
                {#if daylight.length}
                  {@const dPass = daylight.filter((r: DaylightResult) => r.passes).length}
                  {@const dFail = daylight.length - dPass}
                  <div>
                    <button type="button" class="flex items-center gap-2 text-xs font-semibold text-slate-300 mb-2" on:click={() => toggleSection('daylight')}>
                      {#if openSections['daylight']}<ChevronDown class="w-3.5 h-3.5" />{:else}<ChevronRight class="w-3.5 h-3.5" />{/if}
                      Daylight Ratio
                      <span class="text-[10px] font-mono text-slate-500">{dPass}/{daylight.length} pass</span>
                    </button>
                    {#if openSections['daylight'] || dFail > 0}
                      <div class="overflow-auto border border-slate-800 rounded-lg max-h-64">
                        <table class="w-full text-xs">
                          <thead><tr class="bg-slate-800/80">
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Floor</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Room</th>
                            <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400">Floor m²</th>
                            <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400">Window m²</th>
                            <th class="px-3 py-2 text-right text-xs font-semibold text-slate-400">Ratio</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Status</th>
                          </tr></thead>
                          <tbody>
                            {#each [...daylight].sort((a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1)) as r}
                              <tr class="border-b border-slate-800/60 last:border-0">
                                <td class="px-3 py-2 text-xs text-slate-400">{r.storey_name || '—'}</td>
                                <td class="px-3 py-2 text-xs text-white">{(r.space_name || '').slice(0, 35)}</td>
                                <td class="px-3 py-2 text-xs font-mono text-right text-slate-300">{r.floor_area_m2.toFixed(1)}</td>
                                <td class="px-3 py-2 text-xs font-mono text-right text-slate-300">{r.total_window_area_m2.toFixed(2)}</td>
                                <td class="px-3 py-2 text-xs font-mono text-right text-slate-300">{r.daylight_ratio.toFixed(3)}</td>
                                <td class="px-3 py-2 text-xs font-semibold {r.passes ? 'text-emerald-400' : 'text-rose-400'}">{r.passes ? '✓ Pass' : '✗ Fail'}</td>
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
              {#if domain.key === 'fire'}
                {@const fireSep = (result.spatial_checks || {}).fire_separation || []}
                {#if fireSep.length}
                  {@const fPass = fireSep.filter((r: FireSeparationResult) => r.passes).length}
                  {@const fFail = fireSep.length - fPass}
                  <div>
                    <button type="button" class="flex items-center gap-2 text-xs font-semibold text-slate-300 mb-2" on:click={() => toggleSection('fire-sep')}>
                      {#if openSections['fire-sep']}<ChevronDown class="w-3.5 h-3.5" />{:else}<ChevronRight class="w-3.5 h-3.5" />{/if}
                      Fire Separation
                      <span class="text-[10px] font-mono text-slate-500">{fPass}/{fireSep.length} pass</span>
                    </button>
                    {#if openSections['fire-sep'] || fFail > 0}
                      <div class="overflow-auto border border-slate-800 rounded-lg max-h-64">
                        <table class="w-full text-xs">
                          <thead><tr class="bg-slate-800/80">
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Wall</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Between Spaces</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Fire Rating</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Status</th>
                          </tr></thead>
                          <tbody>
                            {#each [...fireSep].sort((a, b) => (a.passes === b.passes ? 0 : a.passes ? 1 : -1)) as r}
                              {@const spaces = (r.adjacent_spaces || []).slice(0, 2).join(', ') + (r.adjacent_spaces?.length > 2 ? ` +${r.adjacent_spaces.length - 2}` : '')}
                              <tr class="border-b border-slate-800/60 last:border-0">
                                <td class="px-3 py-2 text-xs font-mono text-white">{(r.wall_name || '').slice(0, 35)}</td>
                                <td class="px-3 py-2 text-xs text-slate-300">{spaces.slice(0, 50)}</td>
                                <td class="px-3 py-2 text-xs font-mono {r.missing_rating ? 'text-rose-400' : r.passes ? 'text-emerald-400' : 'text-amber-400'}">
                                  {r.fire_rating_raw || '⚠ Not declared'}
                                </td>
                                <td class="px-3 py-2 text-xs font-semibold {r.passes ? 'text-emerald-400' : 'text-rose-400'}">{r.passes ? '✓ Pass' : '✗ Fail'}</td>
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
                    <button type="button" class="flex items-center gap-2 text-xs font-semibold text-slate-300 mb-2" on:click={() => toggleSection('alarms')}>
                      {#if openSections['alarms']}<ChevronDown class="w-3.5 h-3.5" />{:else}<ChevronRight class="w-3.5 h-3.5" />{/if}
                      Alarm Inventory
                      <span class="text-[10px] font-mono text-slate-500">{Object.values(buildingSummary.alarm_counts).reduce((a, b) => a + b, 0)} alarms</span>
                    </button>
                    {#if openSections['alarms']}
                      <div class="flex flex-wrap gap-2">
                        {#each Object.entries(buildingSummary.alarm_counts).sort() as [k, v]}
                          <span class="inline-block px-2.5 py-1 rounded-full text-xs bg-rose-950/60 text-rose-300 border border-rose-800/60 font-medium">{k}: {v}</span>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}
              {/if}

              <!-- Per-rule collapsible sections -->
              {#if activeRules.length === 0}
                <p class="text-xs text-slate-500 italic">No applicable checks found in the rule library for this category.</p>
              {:else}
                {#each activeRules as rule}
                  {@const rKey = `${domain.key}-${rule.rule_ref || rule.property_name}`}
                  {@const rStatus = rule.status || ''}
                  {@const failC = rule.fail_count || 0}
                  {@const passC = rule.pass_count || 0}
                  {@const missC = rule.missing_count || 0}
                  {@const totalC = rule.total_count || 0}
                  {@const summaryTxt = failC || missC ? `${failC} fail · ${passC} pass · ${missC} missing` : `${passC}/${totalC} pass`}
                  {@const ruleLabel = `${rule.rule_ref || ''}  ${(rule.rule_desc || '').slice(0, 65)}`}
                  {@const isRuleOpen = openRules[rKey] || rStatus === 'FAIL' || rStatus === 'MISSING_DATA'}

                  <div class="border border-slate-800/60 rounded-xl overflow-hidden">
                    <button
                      type="button"
                      class="w-full flex items-center justify-between px-3.5 py-2.5 text-left hover:bg-slate-800/30 transition-colors"
                      on:click={() => toggleRule(rKey)}
                    >
                      <div class="flex items-center gap-2 min-w-0">
                        {#if isRuleOpen}<ChevronDown class="w-3.5 h-3.5 text-slate-400 shrink-0" />{:else}<ChevronRight class="w-3.5 h-3.5 text-slate-400 shrink-0" />{/if}
                        <span class="text-xs font-medium text-slate-200 truncate">{ruleLabel}</span>
                      </div>
                      <span class="text-[10px] font-mono text-slate-400 shrink-0 ml-2">{summaryTxt} · {ruleRequiredText(rule)}</span>
                    </button>

                    {#if isRuleOpen}
                      {@const sortedEls = [...(rule.all_elements || [])].sort((a: RuleElementResult, b: RuleElementResult) => {
                        const order: Record<string, number> = { FAIL: 0, MISSING: 1, PASS: 2 };
                        return (order[a.status ?? ''] ?? 3) - (order[b.status ?? ''] ?? 3);
                      })}
                      <div class="overflow-auto border-t border-slate-800/60 max-h-64">
                        <table class="w-full text-xs">
                          <thead><tr class="bg-slate-800/80">
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Element</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Floor / Room</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">GUID</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Actual</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Required</th>
                            <th class="px-3 py-2 text-left text-xs font-semibold text-slate-400">Status</th>
                          </tr></thead>
                          <tbody>
                            {#each sortedEls.slice(0, 50) as el}
                              {@const elStatus = el.status || ''}
                              {@const actualTxt = fmtVal(el.actual) + (rule.unit && el.actual != null ? ` ${rule.unit}` : '')}
                              {@const statusTxt = elStatus === 'FAIL' ? (el.reason || 'fail') : elStatus === 'MISSING' ? 'missing' : '✓ pass'}
                              {@const statusCls = elStatus === 'FAIL' ? 'text-rose-400 font-semibold' : elStatus === 'MISSING' ? 'text-amber-400 font-semibold' : 'text-emerald-400'}
                              {@const rowBg = elStatus === 'FAIL' ? 'bg-rose-950/20' : elStatus === 'MISSING' ? 'bg-amber-950/20' : ''}
                              <tr class="border-b border-slate-800/40 last:border-0 {rowBg}">
                                <td class="px-3 py-2">
                                  <span class="text-xs font-mono text-white">{(el.element_name || '—').slice(0, 32)}</span>
                                </td>
                                <td class="px-3 py-2">
                                  <span class="text-xs text-slate-300 block">{el.storey || '—'}</span>
                                  {#if el.space && el.space !== '—'}
                                    <span class="text-xs text-slate-500 block">{el.space}</span>
                                  {/if}
                                </td>
                                <td class="px-3 py-2"><span class="text-xs font-mono text-slate-500">{(el.guid || '').slice(0, 14)}</span></td>
                                <td class="px-3 py-2 text-xs font-mono text-slate-300 {elStatus === 'FAIL' ? 'text-rose-300 font-semibold' : elStatus === 'MISSING' ? 'text-amber-300 font-semibold' : ''}">{actualTxt}</td>
                                <td class="px-3 py-2 text-xs text-slate-500">{ruleRequiredText(rule)}</td>
                                <td class="px-3 py-2 text-xs {statusCls}">
                                  {statusTxt}
                                  {#if elStatus === 'FAIL' && el.guid && selectedProjectId}
                                    <button
                                      type="button"
                                      class="ml-2 text-blue-400 hover:text-blue-300 hover:underline"
                                      on:click|stopPropagation={() => onSelectProjectForViewer(selectedProjectId!, el.guid, result?.bcf_artifact_id || undefined)}
                                    >View in 3D</button>
                                  {/if}
                                </td>
                              </tr>
                            {/each}
                            {#if sortedEls.length > 50}
                              <tr><td colspan="6" class="px-3 py-2 text-xs text-slate-500 italic">… and {sortedEls.length - 50} more</td></tr>
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
    <div class="p-16 text-center text-xs text-slate-400 space-y-2">
      <div class="animate-spin w-6 h-6 border-2 border-[#0071e3] border-t-transparent rounded-full mx-auto"></div>
      <p>Running Ontario Building Code architectural compliance analysis…</p>
    </div>
  {:else}
    <div class="p-16 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl">
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
