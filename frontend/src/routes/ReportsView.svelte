<script lang="ts">
  import { onMount } from 'svelte';
  import { FileText, Download, CheckCircle2, AlertTriangle, Clock, DollarSign } from 'lucide-svelte';
  import { projectsApi, analyzeApi } from '../lib/api';
  import type { Project, AnalysisResult } from '../lib/types';

  export let initialProjectId: number | null = null;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let result: AnalysisResult | null = null;
  let isLoading = false;

  onMount(async () => {
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
      if (selectedProjectId) {
        await loadReport();
      }
    } catch {
      // ignore
    }
  });

  async function loadReport() {
    if (!selectedProjectId) return;
    isLoading = true;
    try {
      result = await analyzeApi.getResults(selectedProjectId, 'corrosion');
    } catch {
      result = null;
    } finally {
      isLoading = false;
    }
  }

  $: currentProject = projects.find((p) => p.id === selectedProjectId);
</script>

<div class="space-y-6 max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Reports</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">Compliance Reports &amp; Exports</h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Generate and download OpenBIM compliance audit deliverables in BCF 2.1, CSV, and JSON.
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
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
        <div class="flex items-center justify-between">
          <div class="text-xs font-bold uppercase tracking-wider text-blue-400">BCF 2.1 Standard</div>
          <FileText class="w-5 h-5 text-blue-400" />
        </div>
        <div class="text-sm font-semibold text-white">BIM Collaboration Format</div>
        <p class="text-xs text-slate-400">
          ZIP archive containing viewpoint camera vectors, issue markups, and component GUID selections compatible with Solibri, Navisworks, and Revit.
        </p>
        <a
          href={analyzeApi.getExportUrl(selectedProjectId, 'corrosion', 'bcf')}
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white transition-colors w-full justify-center"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Download BCF 2.1 (.bcfzip)</span>
        </a>
      </div>

      <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
        <div class="flex items-center justify-between">
          <div class="text-xs font-bold uppercase tracking-wider text-emerald-400">Spreadsheet</div>
          <FileText class="w-5 h-5 text-emerald-400" />
        </div>
        <div class="text-sm font-semibold text-white">CSV Compliance Export</div>
        <p class="text-xs text-slate-400">
          Structured CSV table with element GUIDs, risk severity bands, engineering mechanisms, and recommended remediation actions.
        </p>
        <a
          href={analyzeApi.getExportUrl(selectedProjectId, 'corrosion', 'csv')}
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors w-full justify-center"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Download CSV Report</span>
        </a>
      </div>

      <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
        <div class="flex items-center justify-between">
          <div class="text-xs font-bold uppercase tracking-wider text-purple-400">Machine Readable</div>
          <FileText class="w-5 h-5 text-purple-400" />
        </div>
        <div class="text-sm font-semibold text-white">JSON Audit Payload</div>
        <p class="text-xs text-slate-400">
          Complete JSON serialization of findings, pipeline timings, model metadata, and per-engine compliance scores.
        </p>
        <a
          href={analyzeApi.getExportUrl(selectedProjectId, 'corrosion', 'json')}
          class="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors w-full justify-center"
        >
          <Download class="w-3.5 h-3.5" />
          <span>Download JSON Payload</span>
        </a>
      </div>
    </div>

    <!-- Impact & Findings Metrics -->
    {#if result}
      <div class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4">
        <h2 class="text-base font-bold text-white tracking-tight">Audit Metrics Summary</h2>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold">Assessed Elements</div>
            <div class="text-2xl font-bold text-white mt-1">{result.element_count}</div>
          </div>
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold">Total Issues</div>
            <div class="text-2xl font-bold text-rose-400 mt-1">{result.issue_stats.total}</div>
          </div>
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold">Estimated Delay</div>
            <div class="text-2xl font-bold text-amber-400 mt-1">162 days</div>
          </div>
          <div class="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <div class="text-xs text-slate-400 uppercase font-semibold">Remediation Cost</div>
            <div class="text-2xl font-bold text-emerald-400 mt-1">£170,600</div>
          </div>
        </div>
      </div>
    {/if}
  {:else}
    <div class="p-16 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl">
      Select a project to generate and export compliance audit deliverables.
    </div>
  {/if}
</div>

