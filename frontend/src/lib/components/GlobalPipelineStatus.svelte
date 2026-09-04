<script lang="ts">
  import { Activity } from "lucide-svelte";
  import { pipelineTracker, avgPipelineProgress } from "../stores/activePipelines.svelte";

  interface Props {
    /** Navigate to the Live Workflow view for a tracked project. */
    onOpen?: (projectId: number) => void;
  }

  let { onOpen }: Props = $props();
</script>

{#if pipelineTracker.tracked.length > 0}
  <div class="hidden items-center gap-1.5 lg:flex">
    {#each pipelineTracker.tracked as run (run.projectId)}
      <button
        type="button"
        onclick={() => onOpen?.(run.projectId)}
        class="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-300 transition-colors hover:bg-blue-500/20"
        title={`${run.projectName} — analysis running`}
      >
        <Activity class="h-3 w-3 animate-pulse" />
        <span class="max-w-[9rem] truncate">{run.projectName}</span>
        <span class="font-mono text-micro text-blue-400">{avgPipelineProgress(run.status)}%</span>
      </button>
    {/each}
  </div>
{/if}
