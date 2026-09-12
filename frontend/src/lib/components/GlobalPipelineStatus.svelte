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
        class="inline-flex items-center gap-1.5 rounded-lg border border-info-border bg-info-bg px-2.5 py-1 text-xs font-medium text-info transition-colors hover:bg-info-bg/80"
        title={`${run.projectName} — analysis running`}
      >
        <Activity class="h-3 w-3 animate-pulse" />
        <span class="max-w-36 truncate">{run.projectName}</span>
        <span class="font-mono text-micro text-info">{avgPipelineProgress(run.status)}%</span>
      </button>
    {/each}
  </div>
{/if}
