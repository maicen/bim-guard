<script lang="ts">
  import { onMount } from 'svelte';
  import {
    LayoutList,
    Play,
    ScanEye,
    CheckCircle2,
    AlertTriangle,
    ShieldAlert,
    Download,
    Layers,
  } from 'lucide-svelte';
  import { projectsApi, analyzeApi } from '../lib/api';
  import type { Project, ArchAnalysisResult } from '../lib/types';

  export let initialProjectId: number | null = null;
  export let onSelectProjectForViewer: (projectId: number, elementGuid?: string) => void;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let isLoading = false;
  let isRunning = false;
  let error = '';

  let result: ArchAnalysisResult | null = null;

  onMount(async () => {
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
      if (selectedProjectId) {
        await runCheck();
      }
    } catch (err: any) {
      error = err.message || 'Failed to load projects';
    }
  });

  async function runCheck() {
    if (!selectedProjectId) return;
    isRunning = true;
    error = '';
    try {
      result = await analyzeApi.runArch(selectedProjectId);
    } catch (err: any) {
      error = err.message || 'Architectural compliance check failed.';
    } finally {
      isRunning = false;
    }
  }

  $: currentProject = projects.find((p) => p.id === selectedProjectId);
</script>

<div class="space-y-6 max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Analysis</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">Architectural Compliance Audit</h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Ontario Building Code Part 9 verification across doors, daylighting, fire separations, travel distance, and stairs.
      </p>
    </div>

    <!-- Project selector & Run button -->
    <div class="flex items-center gap-3">
      <select
        bind:value={selectedProjectId}
        on:change={() => runCheck()}
        class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
      >
        {#each projects as project}
          <option value={project.id}>{project.name}</option>
        {/each}
      </select>

      <button
        type="button"
        disabled={isRunning || !selectedProjectId}
        on:click={runCheck}
        class="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50"
      >
        <Play class="w-3.5 h-3.5" />
        <span>{isRunning ? 'Auditing Code...' : 'Run ARCH Audit'}</span>
      </button>
    </div>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  {#if result}
    <!-- Summary KPI cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Total Findings</div>
        <div class="text-2xl font-bold text-white mt-1">{result.total_issues}</div>
      </div>
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Egress & Travel</div>
        <div class="text-2xl font-bold text-amber-400 mt-1">
          {(result.categories?.egress || []).length}
        </div>
      </div>
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Daylight & Windows</div>
        <div class="text-2xl font-bold text-cyan-400 mt-1">
          {(result.categories?.daylight || []).length}
        </div>
      </div>
      <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
        <div class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Fire Separations</div>
        <div class="text-2xl font-bold text-rose-400 mt-1">
          {(result.categories?.fire || []).length}
        </div>
      </div>
    </div>

    <!-- Category findings -->
    <div class="space-y-6">
      {#each Object.entries(result.categories || {}) as [categoryKey, items]}
        <div class="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-bold text-white capitalize">{categoryKey.replace('_', ' ')} Checks ({items.length})</h3>
          </div>

          {#if items.length === 0}
            <div class="p-4 rounded-xl border border-dashed border-slate-800 text-xs text-slate-500">
              No non-compliance issues reported in this architectural category.
            </div>
          {:else}
            <div class="space-y-2">
              {#each items as item}
                <div class="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-xs">
                  <div class="space-y-0.5 max-w-xl">
                    <div class="font-semibold text-white">{item.title || item.name || 'Architectural non-compliance'}</div>
                    <div class="text-[11px] text-slate-400">{item.description || item.rule || ''}</div>
                    {#if item.element_id}
                      <span class="font-mono text-[10px] text-slate-500">GUID: {item.element_id}</span>
                    {/if}
                  </div>

                  {#if item.element_id && selectedProjectId}
                    <button
                      type="button"
                      on:click={() => onSelectProjectForViewer(selectedProjectId, item.element_id)}
                      class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 hover:text-blue-300 text-xs font-semibold transition-colors shrink-0"
                    >
                      <ScanEye class="w-3.5 h-3.5" />
                      <span>View in 3D</span>
                    </button>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {:else if isRunning}
    <div class="p-16 text-center text-xs text-slate-400 space-y-2">
      <div class="animate-spin w-6 h-6 border-2 border-[#0071e3] border-t-transparent rounded-full mx-auto"></div>
      <p>Running Ontario Building Code architectural compliance analysis...</p>
    </div>
  {:else}
    <div class="p-16 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl">
      Select a project and click "Run ARCH Audit" to inspect building code compliance.
    </div>
  {/if}
</div>

