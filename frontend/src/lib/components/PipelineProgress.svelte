<script lang="ts">
  import type { WorkflowStatus } from '../types';

  export let status: WorkflowStatus | null = null;
  export let isStreaming = false;

  const STAGES = [
    { num: 1, name: 'Validation' },
    { num: 2, name: 'IFC Parsing' },
    { num: 3, name: 'Engine Execution' },
    { num: 4, name: 'Risk Scoring' },
    { num: 5, name: 'Report Assembly' },
    { num: 6, name: 'Export' },
  ];

  // Calculate average progress percent across implemented engines
  $: activeEngines = status ? Object.entries(status.engines).filter(([_, e]) => e.status !== 'not_implemented') : [];
  $: avgProgress = activeEngines.length > 0
    ? Math.round(activeEngines.reduce((acc, [_, e]) => acc + (e.progress_percent || 0), 0) / activeEngines.length)
    : 0;

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

<div class="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur shadow-xl space-y-6">
  <div class="flex items-center justify-between flex-wrap gap-4">
    <div>
      <div class="flex items-center gap-2">
        <h3 class="text-base font-semibold text-white">Live Pipeline Tracker</h3>
        {#if isStreaming}
          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/60">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
            SSE Live Stream
          </span>
        {/if}
      </div>
      <p class="text-xs text-slate-400 mt-1">Real-time stage tracking across compliance engines</p>
    </div>

    <!-- Overall Progress bar -->
    <div class="flex items-center gap-3 min-w-[200px]">
      <div class="flex-1 bg-slate-800 rounded-full h-2.5 overflow-hidden">
        <div
          class="bg-gradient-to-r from-emerald-500 to-teal-400 h-2.5 rounded-full transition-all duration-300"
          style="width: {avgProgress}%"
        ></div>
      </div>
      <span class="text-sm font-semibold text-white">{avgProgress}%</span>
    </div>
  </div>

  <!-- Six Stage Timeline -->
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
    {#each STAGES as stage}
      {@const isDone = avgProgress >= (stage.num / 6) * 100}
      {@const isCurrent = avgProgress > ((stage.num - 1) / 6) * 100 && avgProgress < (stage.num / 6) * 100}
      <div class="p-3 rounded-lg border text-center transition-all {isDone ? 'bg-emerald-950/30 border-emerald-800/40 text-emerald-300' : isCurrent ? 'bg-blue-950/40 border-blue-700/60 text-blue-200 ring-1 ring-blue-500/30' : 'bg-slate-900 border-slate-800 text-slate-500'}">
        <div class="text-xs font-mono font-medium">Stage {stage.num}</div>
        <div class="text-xs font-semibold mt-1 truncate">{stage.name}</div>
      </div>
    {/each}
  </div>

  <!-- Engines Status Breakdown -->
  {#if status && activeEngines.length > 0}
    <div class="space-y-3 pt-2 border-t border-slate-800">
      <h4 class="text-xs uppercase tracking-wider text-slate-400 font-semibold">Engine Execution Matrix</h4>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        {#each Object.entries(status.engines) as [code, engine]}
          <div class="p-3.5 rounded-lg border border-slate-800 bg-slate-950/40 flex items-center justify-between">
            <div>
              <div class="flex items-center gap-2">
                <span class="font-mono text-sm font-bold text-white">{code}</span>
                <span class="text-xs text-slate-300">{engine.label}</span>
              </div>
              <div class="text-xs text-slate-400 mt-1 flex items-center gap-2">
                {#if engine.stage_name}
                  <span>Stage: <strong class="text-slate-200">{engine.stage_name}</strong></span>
                {/if}
                {#if engine.metrics && Object.keys(engine.metrics).length > 0}
                  <span class="text-slate-500">|</span>
                  <span>{JSON.stringify(engine.metrics).slice(0, 40)}</span>
                {/if}
              </div>
            </div>
            <span class="px-2.5 py-1 rounded text-xs font-medium border uppercase tracking-wider {getStatusBadge(engine.status)}">
              {engine.status}
            </span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

