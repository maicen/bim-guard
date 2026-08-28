<script lang="ts">
  import { onMount } from 'svelte';
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
  } from 'lucide-svelte';
  import { analyzeApi, projectsApi } from '../lib/api';
  import type { AnalysisResult, Project, AuditIssue } from '../lib/types';
  import PipelineProgress from '../lib/components/PipelineProgress.svelte';

  export let initialProjectId: number | null = null;
  export let onSelectProjectForViewer: (projectId: number, elementGuid?: string) => void;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let selectedSlug: 'corrosion' | 'seismic' = 'corrosion';
  let isRunning = false;
  let error = '';
  let result: AnalysisResult | null = null;

  // Filter state
  let searchQuery = '';
  let severityFilter = 'all';

  onMount(async () => {
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
      if (selectedProjectId) {
        await fetchResults();
      }
    } catch (err: any) {
      error = err.message || 'Failed to load projects';
    }
  });

  async function fetchResults() {
    if (!selectedProjectId) return;
    try {
      result = await analyzeApi.getResults(selectedProjectId, selectedSlug);
    } catch {
      result = null;
    }
  }

  async function handleRun() {
    if (!selectedProjectId) return;
    isRunning = true;
    error = '';
    result = null;
    try {
      result = await analyzeApi.run(selectedProjectId, selectedSlug);
    } catch (err: any) {
      error = err.message || 'Analysis failed';
    } finally {
      isRunning = false;
    }
  }

  $: currentProject = projects.find((p) => p.id === selectedProjectId);

  $: filteredIssues = (result?.audit_issues || []).filter((issue: AuditIssue) => {
    const matchesSearch =
      searchQuery === '' ||
      issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.rule_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.element_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSeverity =
      severityFilter === 'all' || issue.band === severityFilter;
    return matchesSearch && matchesSeverity;
  });
</script>

<div class="space-y-6 max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Analysis</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">MEP Piping &amp; Seismic Audit</h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Run galvanic, crevice, and microbiological corrosion checks or Blue Halo seismic clearance validation.
      </p>
    </div>

    <!-- Domain switcher & project select -->
    <div class="flex items-center gap-3">
      <!-- Engine toggle -->
      <div class="bg-slate-900 border border-slate-800 p-0.5 rounded-xl flex items-center">
        <button
          type="button"
          on:click={() => {
            selectedSlug = 'corrosion';
            fetchResults();
          }}
          class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all {selectedSlug === 'corrosion' ? 'bg-[#0071e3] text-white shadow-sm' : 'text-slate-400 hover:text-white'}"
        >
          Corrosion (GC/CC/MC)
        </button>
        <button
          type="button"
          on:click={() => {
            selectedSlug = 'seismic';
            fetchResults();
          }}
          class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all {selectedSlug === 'seismic' ? 'bg-[#0071e3] text-white shadow-sm' : 'text-slate-400 hover:text-white'}"
        >
          Seismic Clearance
        </button>
      </div>

      <!-- Project dropdown -->
      <select
        bind:value={selectedProjectId}
        on:change={() => fetchResults()}
        class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
      >
        {#each projects as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>

      <!-- Run Action -->
      <button
        type="button"
        disabled={isRunning || !currentProject?.ifc_file_path}
        on:click={handleRun}
        class="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50"
      >
        <Play class="w-3.5 h-3.5" />
        <span>{isRunning ? 'Analyzing...' : 'Run Audit'}</span>
      </button>
    </div>
  </div>

  {#if currentProject && !currentProject.ifc_file_path}
    <div class="p-4 rounded-2xl bg-amber-950/40 border border-amber-800 text-amber-300 text-xs flex items-center gap-2.5">
      <AlertTriangle class="w-4 h-4 text-amber-400 shrink-0" />
      <span>No IFC model is attached to {currentProject.name}. Upload one in the project registry before running the compliance engine.</span>
    </div>
  {/if}

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  <!-- Real-time pipeline tracker -->
  {#if selectedProjectId && isRunning}
    <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800">
      <PipelineProgress projectId={selectedProjectId} />
    </div>
  {/if}

  {#if result}
    <!-- Summary Stats Row -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase">Total Findings</div>
        <div class="text-2xl font-bold text-white mt-1">{result.issue_stats.total}</div>
      </div>
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase">Critical</div>
        <div class="text-2xl font-bold text-rose-400 mt-1">{result.issue_stats.critical}</div>
      </div>
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase">High Risk</div>
        <div class="text-2xl font-bold text-orange-400 mt-1">{result.issue_stats.high}</div>
      </div>
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase">Medium Risk</div>
        <div class="text-2xl font-bold text-yellow-400 mt-1">{result.issue_stats.medium}</div>
      </div>
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase">Low Risk</div>
        <div class="text-2xl font-bold text-emerald-400 mt-1">{result.issue_stats.low}</div>
      </div>
    </div>

    <!-- Findings Table Card -->
    <div class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 class="text-base font-bold text-white tracking-tight">Audit Findings ({result.audit_issues.length})</h2>
          <p class="text-xs text-slate-400">Detailed component non-compliance and engineering mitigations.</p>
        </div>

        <!-- Export formats -->
        <div class="flex items-center gap-2">
          {#if selectedProjectId}
            <a
              href={analyzeApi.getExportUrl(selectedProjectId, selectedSlug, 'bcf')}
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm transition-all"
            >
              <Download class="w-3.5 h-3.5" />
              <span>Export BCF 2.1</span>
            </a>
            <a
              href={analyzeApi.getExportUrl(selectedProjectId, selectedSlug, 'csv')}
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
            >
              <Download class="w-3.5 h-3.5" />
              <span>CSV</span>
            </a>
            <a
              href={analyzeApi.getExportUrl(selectedProjectId, selectedSlug, 'json')}
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
            >
              <Download class="w-3.5 h-3.5" />
              <span>JSON</span>
            </a>
          {/if}
        </div>
      </div>

      <!-- Filters -->
      <div class="flex flex-col sm:flex-row items-center gap-3 pt-2">
        <div class="relative flex-1 w-full">
          <Search class="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="Search findings by rule, element GUID, or description..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <select
          bind:value={severityFilter}
          class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <!-- Table -->
      <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-950/40">
        {#if filteredIssues.length === 0}
          <div class="p-8 text-center text-xs text-slate-500">
            No compliance issues match your filters.
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
              <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                <tr>
                  <th class="py-3 px-4">Severity</th>
                  <th class="py-3 px-4">Rule / Mechanism</th>
                  <th class="py-3 px-4">Element GUID</th>
                  <th class="py-3 px-4">Finding &amp; Mitigation</th>
                  <th class="py-3 px-4 text-right">3D Action</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each filteredIssues as issue}
                  <tr class="hover:bg-slate-900/60 transition-colors">
                    <td class="py-3 px-4">
                      <span class="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase {issue.band === 'critical' ? 'bg-red-950/60 text-red-400 border border-red-800/60' : issue.band === 'high' ? 'bg-orange-950/60 text-orange-400 border border-orange-800/60' : issue.band === 'medium' ? 'bg-yellow-950/60 text-yellow-400 border border-yellow-800/60' : 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60'}">
                        {issue.band}
                      </span>
                    </td>
                    <td class="py-3 px-4 font-mono">
                      <div class="font-bold text-white text-xs">{issue.rule_id}</div>
                      <div class="text-[10px] text-slate-500">{issue.mechanism}</div>
                    </td>
                    <td class="py-3 px-4 font-mono text-slate-400 text-[11px] truncate max-w-xs">
                      {issue.element_id}
                    </td>
                    <td class="py-3 px-4 max-w-md">
                      <div class="font-semibold text-slate-200">{issue.title}</div>
                      {#if issue.mitigation}
                        <div class="text-[11px] text-slate-400 mt-0.5">{issue.mitigation}</div>
                      {/if}
                    </td>
                    <td class="py-3 px-4 text-right whitespace-nowrap">
                      {#if selectedProjectId && issue.element_id}
                        <button
                          type="button"
                          on:click={() => onSelectProjectForViewer(selectedProjectId, issue.element_id)}
                          class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 hover:text-blue-300 text-xs font-semibold transition-colors"
                        >
                          <ScanEye class="w-3.5 h-3.5" />
                          <span>View in 3D</span>
                        </button>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>
  {:else if !isRunning}
    <div class="p-16 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl">
      Select a project above and click "Run Audit" to assess compliance.
    </div>
  {/if}
</div>
