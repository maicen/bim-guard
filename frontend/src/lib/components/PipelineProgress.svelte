<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import type { WorkflowStatus } from '../types';
  import { analyzeApi } from '../api';
  import { subscribeToPipelineEvents } from '../sse';
  import { Activity, CheckCircle2, Clock, AlertCircle, RefreshCw } from 'lucide-svelte';

  export let projectId: number | null = null;
  export let status: WorkflowStatus | null = null;
  export let isStreaming = false;

  let internalStatus: WorkflowStatus | null = status;
  let unsubscribeSSE: (() => void) | null = null;
  let pollInterval: any = null;

  const STAGES = [
    { num: 1, name: 'Validation', desc: 'Model ingestion & SHA-256 integrity' },
    { num: 2, name: 'IFC Parsing', desc: 'GlobalId dedup & ServiceElement extraction' },
    { num: 3, name: 'Engine Execution', desc: 'GC-001 / CC-001 / MC-001 / SB-001' },
    { num: 4, name: 'Risk Scoring', desc: 'Score → Band normalisation & citations' },
    { num: 5, name: 'Report Assembly', desc: 'Data quality separation & issue assembly' },
    { num: 6, name: 'Export', desc: 'BCF 2.1 / CSV / JSON serialisation' },
  ];

  $: currentStatus = status || internalStatus;

  $: activeEngines = currentStatus
    ? Object.entries(currentStatus.engines).filter(([_, e]) => e.status !== 'not_implemented')
    : [];

  $: avgProgress = activeEngines.length > 0
    ? Math.round(activeEngines.reduce((acc, [_, e]) => acc + (e.progress_percent || 0), 0) / activeEngines.length)
    : 0;

  async function fetchStatus() {
    if (!projectId) return;
    try {
      internalStatus = await analyzeApi.getStatus(projectId);
    } catch {
      // ignore
    }
  }

  function setupSubscription() {
    if (unsubscribeSSE) {
      unsubscribeSSE();
      unsubscribeSSE = null;
    }
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }

    if (!projectId) return;

    fetchStatus();

    try {
      unsubscribeSSE = subscribeToPipelineEvents(projectId, {
        onStatus: (newStatus) => {
          internalStatus = newStatus;
          isStreaming = true;
        },
        onError: () => {
          isStreaming = false;
        },
      });
    } catch {
      isStreaming = false;
    }

    // Fallback light poller
    pollInterval = setInterval(fetchStatus, 3000);
  }

  $: if (projectId) {
    setupSubscription();
  }

  onMount(() => {
    if (projectId) setupSubscription();
  });

  onDestroy(() => {
    if (unsubscribeSSE) unsubscribeSSE();
    if (pollInterval) clearInterval(pollInterval);
  });

  function getStatusBadge(engineStatus: string) {
    switch (engineStatus) {
      case 'complete':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'running':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20 animate-pulse';
      case 'failed':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'not_implemented':
        return 'bg-slate-800 text-slate-400 border-slate-700';
      default:
        return 'bg-slate-800/60 text-slate-400 border-slate-700/60';
    }
  }
</script>

<div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur shadow-xl space-y-6">
  <!-- Header -->
  <div class="flex items-center justify-between flex-wrap gap-4">
    <div>
      <div class="flex items-center gap-2.5">
        <Activity class="w-4 h-4 text-[#0071e3] {avgProgress > 0 && avgProgress < 100 ? 'animate-pulse' : ''}" />
        <h3 class="text-sm font-bold text-white tracking-tight">Real-Time Pipeline Execution Tracker</h3>
        {#if isStreaming}
          <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/60">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
            SSE Live
          </span>
        {/if}
      </div>
      <p class="text-xs text-slate-400 mt-0.5">
        Live per-engine progression across the six compliance stages.
      </p>
    </div>

    <!-- Overall Progress Bar -->
    <div class="flex items-center gap-3 min-w-[220px]">
      <div class="flex-1 bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
        <div
          class="bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400 h-2 rounded-full transition-all duration-300 shadow-sm"
          style="width: {avgProgress}%"
        ></div>
      </div>
      <span class="text-xs font-mono font-bold text-white">{avgProgress}%</span>
    </div>
  </div>

  <!-- Six Stage Visual Timeline -->
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
    {#each STAGES as stage}
      {@const isDone = avgProgress >= (stage.num / 6) * 100}
      {@const isCurrent = avgProgress > ((stage.num - 1) / 6) * 100 && avgProgress < (stage.num / 6) * 100}
      <div class="p-3 rounded-xl border text-left transition-all {isDone ? 'bg-emerald-950/20 border-emerald-800/50 text-emerald-300' : isCurrent ? 'bg-blue-950/40 border-blue-600/70 text-blue-200 ring-1 ring-blue-500/40' : 'bg-slate-950/60 border-slate-800/80 text-slate-500'}">
        <div class="flex items-center justify-between">
          <span class="text-[10px] font-mono uppercase font-bold tracking-wider opacity-80">Stage {stage.num}</span>
          {#if isDone}
            <CheckCircle2 class="w-3.5 h-3.5 text-emerald-400" />
          {:else if isCurrent}
            <RefreshCw class="w-3.5 h-3.5 text-blue-400 animate-spin" />
          {:else}
            <Clock class="w-3.5 h-3.5 opacity-40" />
          {/if}
        </div>
        <div class="text-xs font-bold mt-1 text-white truncate">{stage.name}</div>
        <div class="text-[10px] text-slate-400 line-clamp-1 mt-0.5 opacity-70">{stage.desc}</div>
      </div>
    {/each}
  </div>

  <!-- Engine Execution Matrix -->
  {#if currentStatus && Object.keys(currentStatus.engines || {}).length > 0}
    <div class="space-y-3 pt-2 border-t border-slate-800/80">
      <div class="flex items-center justify-between">
        <h4 class="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Engine Execution Matrix</h4>
        <span class="text-[10px] text-slate-500 font-mono">Phase 6–9 Pipeline Engines</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        {#each Object.entries(currentStatus.engines) as [code, engine]}
          <div class="p-3.5 rounded-xl border border-slate-800 bg-slate-950/50 flex flex-col justify-between gap-2.5 hover:border-slate-700 transition-colors">
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded-md bg-slate-800/80 text-white font-mono text-xs font-bold border border-slate-700">{code}</span>
                <span class="text-xs font-semibold text-slate-200">{engine.label || code}</span>
              </div>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold border uppercase tracking-wider {getStatusBadge(engine.status)}">
                {engine.status}
              </span>
            </div>

            <!-- Engine metrics & Stage -->
            <div class="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-900">
              <div class="flex items-center gap-2">
                {#if engine.stage_name}
                  <span>Stage: <strong class="text-slate-300">{engine.stage_name}</strong></span>
                {:else}
                  <span class="text-slate-500">Idle / Ready</span>
                {/if}
              </div>
              {#if engine.metrics && Object.keys(engine.metrics).length > 0}
                <div class="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                  {#if engine.metrics.elements_total}
                    <span>{engine.metrics.elements_total} elements</span>
                  {/if}
                  {#if engine.metrics.findings !== undefined}
                    <span>• {engine.metrics.findings} findings</span>
                  {/if}
                  {#if engine.metrics.data_quality !== undefined}
                    <span>• {engine.metrics.data_quality} DQ</span>
                  {/if}
                </div>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

