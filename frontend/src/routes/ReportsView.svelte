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
  } from "lucide-svelte";
  import { projectsApi, analyzeApi, bcfApi, rulesApi } from "../lib/api";
  import type { Project, AnalysisResult, BcfArtifact, BCFTopicResponse } from "../lib/types";

  export let initialProjectId: number | null = null;
  export let onSelectProjectForViewer:
    | ((projectId: number, elementGuid?: string, bcfArtifactId?: number) => void)
    | undefined = undefined;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let result: AnalysisResult | null = null;
  let isLoading = false;

  // ARCH BCF Artifacts
  let bcfArtifacts: BcfArtifact[] = [];
  let isBcfLoading = false;
  let filterToSelectedProject = false;

  // Live BCF REST Topics
  let bcfTopics: BCFTopicResponse[] = [];
  let isTopicsLoading = false;
  let activeTab: "live_bcf" | "artifacts" = "live_bcf";

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

  $: displayedBcfArtifacts =
    filterToSelectedProject && selectedProjectId
      ? bcfArtifacts.filter((a) => a.project_id === selectedProjectId)
      : bcfArtifacts;

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
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div
        class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
      >
        Reports
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        Compliance Reports &amp; Exports
      </h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Generate and download OpenBIM compliance audit deliverables in BCF 2.1,
        CSV, and JSON.
      </p>
    </div>

    <!-- Project Selector -->
    <div class="flex items-center gap-2">
      <select
        bind:value={selectedProjectId}
        on:change={() => loadReport()}
        class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
      >
        {#each projects as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if selectedProjectId}
    <!-- Export Formats Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3 flex flex-col justify-between"
      >
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <div class="text-xs font-bold uppercase tracking-wider text-blue-400">
              BCF 2.1 Standard
            </div>
            <FileText class="w-5 h-5 text-blue-400" />
          </div>
          <div class="text-sm font-semibold text-white">
            BIM Collaboration Format
          </div>
          <p class="text-xs text-slate-400">
            ZIP archive with camera viewpoints, issue markups, and component GUIDs for Solibri, Navisworks, and Revit.
          </p>
        </div>
        <a
          href={analyzeApi.getExportUrl(selectedProjectId, "corrosion", "bcf")}
          class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white transition-colors w-full justify-center"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Download BCF 2.1 (.bcfzip)</span>
        </a>
      </div>

      <div
        class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3 flex flex-col justify-between"
      >
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <div class="text-xs font-bold uppercase tracking-wider text-amber-400">
              buildingSMART IDS 1.0
            </div>
            <Shield class="w-5 h-5 text-amber-400" />
          </div>
          <div class="text-sm font-semibold text-white">
            Information Delivery Spec
          </div>
          <p class="text-xs text-slate-400">
            Official buildingSMART IDS 0.9.6 / 1.0 XML deliverable with multi-facet LOIN rules and numerical tolerances.
          </p>
        </div>
        <a
          href={rulesApi.getIdsExportUrl()}
          download="bimguard_rules.ids"
          class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white transition-colors w-full justify-center"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Download IDS 1.0 (.ids)</span>
        </a>
      </div>

      <div
        class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3 flex flex-col justify-between"
      >
        <div class="space-y-2">
          <div
            class="text-xs font-bold uppercase tracking-wider text-emerald-400"
          >
            Spreadsheet
          </div>
          <FileText class="w-5 h-5 text-emerald-400" />
        </div>
        <div class="text-sm font-semibold text-white">
          CSV Compliance Export
        </div>
        <p class="text-xs text-slate-400">
          Structured CSV table with element GUIDs, risk severity bands, mechanisms, and recommended remediation actions.
        </p>
        <a
          href={analyzeApi.getExportUrl(selectedProjectId, "corrosion", "csv")}
          class="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors w-full justify-center"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Download CSV Report</span>
        </a>
      </div>

      <div
        class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3 flex flex-col justify-between"
      >
        <div class="space-y-2">
          <div
            class="text-xs font-bold uppercase tracking-wider text-purple-400"
          >
            Machine Readable
          </div>
          <FileText class="w-5 h-5 text-purple-400" />
        </div>
        <div class="text-sm font-semibold text-white">JSON Audit Payload</div>
        <p class="text-xs text-slate-400">
          Complete JSON serialization of findings, pipeline timings, model metadata, and per-engine compliance scores.
        </p>
        <a
          href={analyzeApi.getExportUrl(selectedProjectId, "corrosion", "json")}
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors w-full justify-center"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Download JSON Payload</span>
        </a>
      </div>
    </div>

    <!-- Impact & Findings Metrics -->
    {#if result}
      <div
        class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4"
      >
        <h2 class="text-base font-bold text-white tracking-tight">
          Audit Metrics Summary
        </h2>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold">
              Assessed Elements
            </div>
            <div class="text-2xl font-bold text-white mt-1">
              {result.element_count}
            </div>
          </div>
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold">
              Total Issues
            </div>
            <div class="text-2xl font-bold text-rose-400 mt-1">
              {result.issue_stats.total}
            </div>
          </div>
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold flex items-center justify-between">
              <span>Estimated Delay</span>
              <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-950/60 text-amber-400 border border-amber-800/50">Placeholder</span>
            </div>
            <div class="text-2xl font-bold text-amber-400 mt-1">162 days</div>
          </div>
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold flex items-center justify-between">
              <span>Remediation Cost</span>
              <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-800/50">Placeholder</span>
            </div>
            <div class="text-2xl font-bold text-emerald-400 mt-1">£170,600</div>
          </div>
        </div>
      </div>
    {/if}

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
            <h2 class="text-base font-bold text-white tracking-tight">
              buildingSMART BCF Collaboration Hub
            </h2>
            <span
              class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700"
            >
              {activeTab === 'live_bcf' ? `${bcfTopics.length} Live Topics` : `${displayedBcfArtifacts.length} Artifacts`}
            </span>
          </div>
          <p class="text-xs text-slate-400 mt-1">
            Bidirectional BCF REST API v2.1/v3.0 live topics exchange and persisted BCF zip deliverables with ISO 19650 governance tags.
          </p>
        </div>

        <!-- Tab & Refresh Controls -->
        <div class="flex items-center gap-2.5 shrink-0">
          <div
            class="flex items-center rounded-xl bg-slate-950 p-1 border border-slate-800 text-xs"
          >
            <button
              type="button"
              on:click={() => (activeTab = "live_bcf")}
              class="px-3 py-1 rounded-lg font-medium transition-colors {activeTab === 'live_bcf'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white'}"
            >
              Live BCF 2.1 Topics
            </button>
            <button
              type="button"
              on:click={() => (activeTab = "artifacts")}
              class="px-3 py-1 rounded-lg font-medium transition-colors {activeTab === 'artifacts'
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:text-white'}"
            >
              BCF Zip Artifacts
            </button>
          </div>

          <button
            type="button"
            on:click={() => {
              if (activeTab === 'live_bcf') loadBcfTopics();
              else loadBcfArtifacts();
            }}
            disabled={isTopicsLoading || isBcfLoading}
            class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition-colors disabled:opacity-50"
            title="Refresh Deliverables"
          >
            <RefreshCw
              class="w-3.5 h-3.5 {isTopicsLoading || isBcfLoading ? 'animate-spin' : ''}"
            />
          </button>
        </div>
      </div>

      {#if activeTab === "live_bcf"}
        <!-- Live BCF REST Topics Tab -->
        {#if isTopicsLoading && bcfTopics.length === 0}
          <div class="p-8 text-center text-xs text-slate-400">
            <div
              class="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"
            ></div>
            Querying /api/bcf/v2.1/projects/{selectedProjectId}/topics...
          </div>
        {:else if bcfTopics.length === 0}
          <div
            class="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl space-y-2"
          >
            <div>No live BCF topics synced for {currentProject?.name || "this project"}.</div>
            <div class="text-[11px] text-slate-600">Run an Architectural Compliance or Corrosion audit to publish live BCF REST topics.</div>
          </div>
        {:else}
          <div class="overflow-x-auto rounded-xl border border-slate-800/80">
            <table class="w-full text-left text-xs border-collapse">
              <thead>
                <tr
                  class="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-semibold uppercase tracking-wider text-[10px]"
                >
                  <th class="py-3 px-4">Topic GUID</th>
                  <th class="py-3 px-4">Title &amp; Type</th>
                  <th class="py-3 px-4">Status &amp; Priority</th>
                  <th class="py-3 px-4">ISO 19650 Governance</th>
                  <th class="py-3 px-4">Elements</th>
                  <th class="py-3 px-4">Viewpoints</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each bcfTopics as topic}
                  <tr class="hover:bg-slate-900/60 transition-colors">
                    <td class="py-3 px-4 font-mono text-[11px] text-slate-400">
                      {topic.topic_guid.substring(0, 8)}...
                    </td>
                    <td class="py-3 px-4">
                      <div class="font-medium text-white">{topic.title}</div>
                      <div class="text-[10px] text-slate-400">{topic.topic_type || 'Clash / Compliance'}</div>
                    </td>
                    <td class="py-3 px-4">
                      <div class="flex items-center gap-1.5">
                        <span
                          class="px-2 py-0.5 rounded-full text-[10px] font-semibold border {topic.topic_status === 'Open'
                            ? 'bg-rose-950/60 text-rose-300 border-rose-800'
                            : 'bg-emerald-950/60 text-emerald-300 border-emerald-800'}"
                        >
                          {topic.topic_status || 'Open'}
                        </span>
                        <span class="text-[10px] text-slate-400 font-medium">
                          {topic.priority || 'Normal'}
                        </span>
                      </div>
                    </td>
                    <td class="py-3 px-4">
                      <div class="flex items-center gap-1 text-[10px]">
                        <span class="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 font-semibold">
                          {topic.suitability_code || 'S0'}
                        </span>
                        <span class="px-1.5 py-0.5 rounded bg-slate-800 text-blue-400 font-semibold">
                          {topic.revision_code || 'P01.01'}
                        </span>
                        <span class="px-1.5 py-0.5 rounded bg-slate-800 text-emerald-400 font-semibold">
                          {topic.cde_state || 'WIP'}
                        </span>
                      </div>
                    </td>
                    <td class="py-3 px-4 font-mono text-slate-300">
                      {topic.component_guids ? topic.component_guids.length : 0} GUID{topic.component_guids?.length === 1 ? '' : 's'}
                    </td>
                    <td class="py-3 px-4">
                      <span class="inline-flex items-center gap-1 text-slate-300 text-[11px]">
                        <Camera class="w-3 h-3 text-blue-400" />
                        <span>{topic.viewpoints_count || 1}</span>
                      </span>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      {:else}
        <!-- Archived BCF Zip Artifacts Tab -->
        {#if selectedProjectId}
          <div class="flex items-center justify-between pb-1">
            <div class="flex items-center rounded-xl bg-slate-950 p-1 border border-slate-800 text-xs">
              <button
                type="button"
                on:click={() => (filterToSelectedProject = false)}
                class="px-2.5 py-1 rounded-lg font-medium transition-colors {!filterToSelectedProject
                  ? 'bg-slate-800 text-white'
                  : 'text-slate-400 hover:text-white'}"
              >
                All Projects
              </button>
              <button
                type="button"
                on:click={() => (filterToSelectedProject = true)}
                class="px-2.5 py-1 rounded-lg font-medium transition-colors {filterToSelectedProject
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'}"
              >
                {currentProject?.name || "Selected"}
              </button>
            </div>
          </div>
        {/if}

      {#if isBcfLoading && bcfArtifacts.length === 0}
        <div class="p-8 text-center text-xs text-slate-400">
          <div
            class="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"
          ></div>
          Loading BCF artifacts…
        </div>
      {:else if displayedBcfArtifacts.length === 0}
        <div
          class="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl"
        >
          {filterToSelectedProject
            ? `No BCF reports found for ${currentProject?.name || "this project"}. Run an ARCH Compliance Audit to generate one.`
            : "No persisted BCF artifacts found. Run an Architectural Compliance Audit to generate reports."}
        </div>
      {:else}
        <div class="overflow-x-auto rounded-xl border border-slate-800/80">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr
                class="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-semibold uppercase tracking-wider text-[10px]"
              >
                <th class="py-3 px-4">ID</th>
                <th class="py-3 px-4">Project</th>
                <th class="py-3 px-4">Artifact / Filename</th>
                <th class="py-3 px-4">Issues</th>
                <th class="py-3 px-4">Size</th>
                <th class="py-3 px-4">Date</th>
                <th class="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#each displayedBcfArtifacts as artifact}
                <tr class="hover:bg-slate-900/60 transition-colors">
                  <td class="py-3 px-4 font-mono text-slate-500">#{artifact.id}</td>
                  <td class="py-3 px-4 font-medium text-white">
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
                      class="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold border {artifact.issue_count > 0
                        ? 'bg-rose-950/60 text-rose-300 border-rose-800'
                        : 'bg-emerald-950/60 text-emerald-300 border-emerald-800'}"
                    >
                      {artifact.issue_count} issue{artifact.issue_count === 1 ? "" : "s"}
                    </span>
                  </td>
                  <td class="py-3 px-4 font-mono text-slate-400">
                    {formatBytes(artifact.byte_size)}
                  </td>
                  <td class="py-3 px-4 text-slate-400">
                    {formatDate(artifact.created_at)}
                  </td>
                  <td class="py-3 px-4 text-right">
                    <div class="inline-flex items-center gap-2">
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
                          View in 3D
                        </button>
                      {/if}
                      <a
                        href={analyzeApi.getBcfArtifactUrl(artifact.id)}
                        download
                        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 transition-colors"
                        title="Download BCF 2.1 Zip"
                      >
                        <Download class="w-3.5 h-3.5" />
                        Download
                      </a>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
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
