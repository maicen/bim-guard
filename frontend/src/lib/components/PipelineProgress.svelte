<script lang="ts">
  import { run } from "svelte/legacy";

  import { onDestroy, untrack } from "svelte";
  import type { WorkflowStatus } from "../types";
  import { analyzeApi } from "../api";
  import { subscribeToPipelineEvents } from "../sse";
  import { Activity, CheckCircle2, Clock, AlertCircle, RefreshCw } from "lucide-svelte";

  interface Props {
    projectId?: number | null;
    status?: WorkflowStatus | null;
    isStreaming?: boolean;
  }

  let { projectId = null, status = null, isStreaming = $bindable(false) }: Props = $props();

  // Seeded once from the prop; `currentStatus` below always prefers the live
  // prop, and this holds the SSE-fed value when no prop is supplied.
  let internalStatus: WorkflowStatus | null = $state(untrack(() => status));
  let unsubscribeSSE: (() => void) | null = null;
  let pollInterval: any = null;

  const STAGES = [
    { num: 1, name: "Validation", desc: "Model ingestion & SHA-256 integrity" },
    { num: 2, name: "IFC Parsing", desc: "GlobalId dedup & ServiceElement extraction" },
    { num: 3, name: "Engine Execution", desc: "GC-001 / CC-001 / MC-001 / SB-001" },
    { num: 4, name: "Risk Scoring", desc: "Score → Band normalisation & citations" },
    { num: 5, name: "Report Assembly", desc: "Data quality separation & issue assembly" },
    { num: 6, name: "Export", desc: "BCF 2.1 / CSV / JSON serialisation" },
  ];

  let currentStatus = $derived(status || internalStatus);

  let activeEngines = $derived(
    currentStatus
      ? Object.entries(currentStatus.engines).filter(([_, e]) => e.status !== "not_implemented")
      : [],
  );

  let avgProgress = $derived(
    activeEngines.length > 0
      ? Math.round(
          activeEngines.reduce((acc, [_, e]) => acc + (e.progress_percent || 0), 0) /
            activeEngines.length,
        )
      : 0,
  );

  async function fetchStatus() {
    if (!projectId) return;
    try {
      internalStatus = await analyzeApi.getStatus(projectId);
    } catch {
      // Polled every 3s as an SSE fallback; a transient miss is recovered by
      // the next tick, and the stream indicator already shows the degraded state.
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
        onOpen: () => {
          isStreaming = true;
        },
        onStatus: (newStatus) => {
          internalStatus = newStatus;
          isStreaming = true;
        },
        onError: () => {
          isStreaming = false;
        },
      });
    } catch {
      // EventSource could not be opened; the poller below keeps the view live
      // and `isStreaming` drives the "reconnecting" indicator.
      isStreaming = false;
    }

    // Poll only as a fallback. Previously this ran unconditionally alongside a
    // healthy stream, costing ~20 redundant status requests a minute; now each
    // tick short-circuits while the stream is delivering.
    pollInterval = setInterval(() => {
      if (!isStreaming) fetchStatus();
    }, 3000);
  }

  // Runs on first render and on every projectId change; setupSubscription
  // tears down any previous stream first. onMount used to call this a second
  // time, rebuilding the EventSource immediately after it was opened.
  run(() => {
    if (projectId) {
      setupSubscription();
    }
  });

  onDestroy(() => {
    if (unsubscribeSSE) unsubscribeSSE();
    if (pollInterval) clearInterval(pollInterval);
  });

  function getStatusBadge(engineStatus: string) {
    switch (engineStatus) {
      case "complete":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "running":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20 animate-pulse";
      case "failed":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      case "not_implemented":
        return "bg-slate-800 text-slate-400 border-slate-700";
      default:
        return "bg-slate-800/60 text-slate-400 border-slate-700/60";
    }
  }
</script>

<div
  class="space-y-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl backdrop-blur"
>
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <div class="flex items-center gap-2.5">
        <Activity
          class="h-4 w-4 text-accent {avgProgress > 0 && avgProgress < 100 ? 'animate-pulse' : ''}"
        />
        <h3 class="text-sm font-bold tracking-tight text-slate-50">
          Real-Time Pipeline Execution Tracker
        </h3>
        {#if isStreaming}
          <span
            class="inline-flex items-center gap-1.5 rounded-md border border-emerald-800/60 bg-emerald-950/60 px-2 py-0.5 text-micro font-semibold text-emerald-400"
          >
            <span class="h-1.5 w-1.5 animate-ping rounded-full bg-emerald-400"></span>
            SSE Live
          </span>
        {/if}
      </div>
      <p class="mt-0.5 text-xs text-slate-400">
        Live per-engine progression across the six compliance stages.
      </p>
    </div>

    <!-- Overall Progress Bar -->
    <div class="flex min-w-[220px] items-center gap-3">
      <div class="h-2 flex-1 overflow-hidden rounded-full border border-slate-800 bg-slate-950">
        <div
          class="h-2 rounded-full bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400 shadow-sm transition-all duration-300"
          style="width: {avgProgress}%"
        ></div>
      </div>
      <span class="font-mono text-xs font-bold text-slate-50">{avgProgress}%</span>
    </div>
  </div>

  <!-- Six Stage Visual Timeline -->
  <div class="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
    {#each STAGES as stage (stage.name)}
      {@const isDone = avgProgress >= (stage.num / 6) * 100}
      {@const isCurrent =
        avgProgress > ((stage.num - 1) / 6) * 100 && avgProgress < (stage.num / 6) * 100}
      <div
        class="rounded-xl border p-3 text-left transition-all {isDone
          ? 'border-emerald-800/50 bg-emerald-950/20 text-emerald-300'
          : isCurrent
            ? 'border-blue-600/70 bg-blue-950/40 text-blue-200 ring-1 ring-blue-500/40'
            : 'border-slate-800/80 bg-slate-950/60 text-slate-500'}"
      >
        <div class="flex items-center justify-between">
          <span class="font-mono text-micro font-bold uppercase tracking-wider opacity-80"
            >Stage {stage.num}</span
          >
          {#if isDone}
            <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
          {:else if isCurrent}
            <RefreshCw class="h-3.5 w-3.5 animate-spin text-blue-400" />
          {:else}
            <Clock class="h-3.5 w-3.5 opacity-40" />
          {/if}
        </div>
        <div class="mt-1 truncate text-xs font-bold text-slate-50">{stage.name}</div>
        <div class="mt-0.5 line-clamp-1 text-micro text-slate-400 opacity-70">{stage.desc}</div>
      </div>
    {/each}
  </div>

  <!-- Engine Execution Matrix -->
  {#if currentStatus && Object.keys(currentStatus.engines || {}).length > 0}
    <div class="space-y-3 border-t border-slate-800/80 pt-2">
      <div class="flex items-center justify-between">
        <h4 class="text-caption font-semibold uppercase tracking-wider text-slate-400">
          Engine Execution Matrix
        </h4>
        <span class="font-mono text-micro text-slate-500">Phase 6–9 Pipeline Engines</span>
      </div>
      <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
        {#each Object.entries(currentStatus.engines) as [code, engine] (code)}
          <div
            class="flex flex-col justify-between gap-2.5 rounded-xl border border-slate-800 bg-slate-950/50 p-3.5 transition-colors hover:border-slate-700"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span
                  class="rounded-md border border-slate-700 bg-slate-800/80 px-2 py-0.5 font-mono text-xs font-bold text-slate-50"
                  >{code}</span
                >
                <span class="text-xs font-semibold text-slate-200">{engine.label || code}</span>
              </div>
              <span
                class="rounded-md border px-2 py-0.5 text-micro font-semibold uppercase tracking-wider {getStatusBadge(
                  engine.status,
                )}"
              >
                {engine.status}
              </span>
            </div>

            <!-- Engine metrics & Stage -->
            <div
              class="flex items-center justify-between border-t border-slate-900 pt-1 text-caption text-slate-400"
            >
              <div class="flex items-center gap-2">
                {#if engine.stage_name}
                  <span>Stage: <strong class="text-slate-300">{engine.stage_name}</strong></span>
                {:else}
                  <span class="text-slate-500">Idle / Ready</span>
                {/if}
              </div>
              {#if engine.metrics && Object.keys(engine.metrics).length > 0}
                <div class="flex items-center gap-2 font-mono text-micro text-slate-400">
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
