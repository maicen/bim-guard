<script lang="ts">
  import { onMount } from "svelte";
  import {
    Workflow,
    Activity,
    CheckCircle2,
    Clock,
    AlertCircle,
  } from "lucide-svelte";
  import { projectsApi } from "../lib/api";
  import type { Project } from "../lib/types";
  import PipelineProgress from "../lib/components/PipelineProgress.svelte";

  export let initialProjectId: number | null = null;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let isLoading = false;

  onMount(async () => {
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
    } catch {
      // ignore
    }
  });
</script>

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div
        class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
      >
        Workflow
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        Live Pipeline Tracker
      </h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Monitor real-time engine execution, stage transitions, and performance
        metrics via Server-Sent Events (SSE).
      </p>
    </div>

    <!-- Project Selector -->
    <div class="flex items-center gap-2">
      <select
        bind:value={selectedProjectId}
        class="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
      >
        {#each projects as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if selectedProjectId}
    <div
      class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-6"
    >
      <div
        class="flex items-center justify-between border-b border-slate-800 pb-4"
      >
        <div class="flex items-center gap-2">
          <Activity class="w-5 h-5 text-emerald-400 animate-pulse" />
          <h2 class="text-base font-bold text-white tracking-tight">
            Active Engine Pipeline
          </h2>
        </div>
        <div class="text-xs text-slate-400">
          Listening to <code class="font-mono text-slate-300"
            >/api/events/{selectedProjectId}</code
          >
        </div>
      </div>

      <PipelineProgress projectId={selectedProjectId} />
    </div>
  {:else}
    <div
      class="p-16 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-2xl"
    >
      Select a project to inspect its live pipeline events.
    </div>
  {/if}
</div>
