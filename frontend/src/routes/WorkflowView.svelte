<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { Workflow, Activity, CheckCircle2, Clock, AlertCircle } from "lucide-svelte";
  import { projectsApi } from "../lib/api";
  import type { Project } from "../lib/types";
  import PipelineProgress from "../lib/components/PipelineProgress.svelte";
  import { toasts } from "../lib/toast.svelte";

  interface Props {
    initialProjectId?: number | null;
  }

  let { initialProjectId = null }: Props = $props();

  let projects: Project[] = $state([]);
  // These `initial*` props seed local state once. The component is mounted
  // inside App's view switch, so it remounts whenever the target changes;
  // untrack states that the one-time read is deliberate.
  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  let isLoading = false;

  onMount(async () => {
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
    } catch (err) {
      // Without this the user just gets an empty project picker and no reason.
      toasts.fromError(err, "Could not load the project list.");
    }
  });
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <div class="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
    <div>
      <div class="mb-1 text-xs font-bold uppercase tracking-widest text-slate-400">Workflow</div>
      <h1 class="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">
        Live Pipeline Tracker
      </h1>
      <p class="text-xs text-slate-400 sm:text-sm">
        Monitor real-time engine execution, stage transitions, and performance metrics via
        Server-Sent Events (SSE).
      </p>
    </div>

    <!-- Project Selector -->
    <div class="flex items-center gap-2">
      <select
        bind:value={selectedProjectId}
        class="rounded-xl border border-slate-800 bg-slate-900 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
      >
        {#each projects as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if selectedProjectId}
    <div class="space-y-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <div class="flex items-center justify-between border-b border-slate-800 pb-4">
        <div class="flex items-center gap-2">
          <Activity class="h-5 w-5 animate-pulse text-emerald-400" />
          <h2 class="text-base font-bold tracking-tight text-slate-50">Active Engine Pipeline</h2>
        </div>
        <div class="text-xs text-slate-400">
          Listening to <code class="font-mono text-slate-300">/api/events/{selectedProjectId}</code>
        </div>
      </div>

      <PipelineProgress projectId={selectedProjectId} />
    </div>
  {:else}
    <div
      class="rounded-2xl border border-dashed border-slate-800 p-16 text-center text-xs text-slate-500"
    >
      Select a project to inspect its live pipeline events.
    </div>
  {/if}
</div>
