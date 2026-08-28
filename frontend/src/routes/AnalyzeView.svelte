<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { analyzeApi, projectsApi } from '../lib/api';
  import { subscribeToPipelineEvents } from '../lib/sse';
  import type { AnalysisResult, Project, WorkflowStatus } from '../lib/types';
  import PipelineProgress from '../lib/components/PipelineProgress.svelte';
  import IssueTable from '../lib/components/IssueTable.svelte';
  import ExportActions from '../lib/components/ExportActions.svelte';

  export let initialProjectId: number | null = null;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let selectedSlug: 'corrosion' | 'seismic' = 'corrosion';

  let running = false;
  let error = '';
  let analysisResult: AnalysisResult | null = null;
  let workflowStatus: WorkflowStatus | null = null;
  let isStreaming = false;

  let unsubscribeSSE: (() => void) | null = null;

  async function loadProjects() {
    try {
      const res = await projectsApi.list();
      projects = res.projects;
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
      if (selectedProjectId) {
        setupSSE(selectedProjectId);
        fetchExistingResults();
      }
    } catch (err: any) {
      error = err.message || 'Failed to load projects.';
    }
  }

  function setupSSE(projectId: number) {
    if (unsubscribeSSE) {
      unsubscribeSSE();
      unsubscribeSSE = null;
    }
    isStreaming = true;
    unsubscribeSSE = subscribeToPipelineEvents(projectId, {
      onStatus: (st) => {
        workflowStatus = st;
      },
      onEvent: (evt) => {
        // When engine completes, re-fetch findings
        if (evt.event_type === 'engine_complete') {
          fetchExistingResults();
        }
      },
      onError: () => {
        isStreaming = false;
      },
    });
  }

  async function fetchExistingResults() {
    if (!selectedProjectId) return;
    try {
      const res = await analyzeApi.getResults(selectedProjectId, selectedSlug);
      if (res && res.audit_issues) {
        analysisResult = res;
      }
    } catch {
      // no cached results yet
    }
  }

  async function handleRunAnalysis() {
    if (!selectedProjectId) return;
    running = true;
    error = '';
    analysisResult = null;

    try {
      setupSSE(selectedProjectId);
      const res = await analyzeApi.run(selectedProjectId, selectedSlug);
      analysisResult = res;
    } catch (err: any) {
      error = err.message || 'Analysis run failed.';
    } finally {
      running = false;
    }
  }

  function onProjectChange() {
    if (selectedProjectId) {
      analysisResult = null;
      setupSSE(selectedProjectId);
      fetchExistingResults();
    }
  }

  onMount(() => {
    loadProjects();
  });

  onDestroy(() => {
    if (unsubscribeSSE) {
      unsubscribeSSE();
    }
  });
</script>

<div class="space-y-6">
  <!-- Controls Card -->
  <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur shadow-xl space-y-4">
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">Compliance Audit Center</h1>
        <p class="text-xs text-slate-400 mt-0.5">Run automated physics & clearance engines with real-time SSE streaming</p>
      </div>

      <div class="flex items-center gap-3 flex-wrap">
        <!-- Project select -->
        <div>
          <select
            bind:value={selectedProjectId}
            on:change={onProjectChange}
            class="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
          >
            {#each projects as proj}
              <option value={proj.id}>{proj.name} (#{proj.id})</option>
            {/each}
          </select>
        </div>

        <!-- Analysis Slug select -->
        <div>
          <select
            bind:value={selectedSlug}
            on:change={fetchExistingResults}
            class="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="corrosion">Corrosion (GC-001, CC-001, MC-001)</option>
            <option value="seismic">Seismic Clearance (Blue Halo)</option>
          </select>
        </div>

        <!-- Run button -->
        <button
          on:click={handleRunAnalysis}
          disabled={running || !selectedProjectId}
          class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold shadow-lg shadow-emerald-600/20 transition-all"
        >
          {#if running}
            <svg class="animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            Auditing IFC...
          {:else}
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            Execute Audit
          {/if}
        </button>
      </div>
    </div>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-sm">
      {error}
    </div>
  {/if}

  <!-- Live SSE Pipeline Progress Tracker -->
  <PipelineProgress status={workflowStatus} {isStreaming} />

  <!-- Findings Table & Exports -->
  {#if analysisResult}
    <div class="space-y-4">
      <div class="flex items-center justify-between flex-wrap gap-4 pt-2">
        <h2 class="text-lg font-bold text-white">
          Audit Findings ({analysisResult.element_count} Issues)
        </h2>
        {#if selectedProjectId}
          <ExportActions projectId={selectedProjectId} slug={selectedSlug} />
        {/if}
      </div>

      <IssueTable
        issues={analysisResult.audit_issues}
        stats={analysisResult.issue_stats}
      />
    </div>
  {/if}
</div>

