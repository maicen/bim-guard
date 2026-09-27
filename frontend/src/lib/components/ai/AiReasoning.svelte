<!--
  AiReasoning — collapsible reasoning & chain-of-thought display.
  Inspired by shadcn.io/ai/reasoning & ai/chain-of-thought:
  Presents the sequential milestones taken by Graph-RAG during retrieval
  and reasoning, keeping the main response clean while offering deep explainability.
-->
<script lang="ts">
  import { untrack } from "svelte";
  import { Brain, CheckCircle2, ChevronDown, ChevronRight, Loader2, XCircle } from "lucide-svelte";
  import type { GraphRagStep } from "../../types";

  interface Props {
    steps: GraphRagStep[];
    isStreaming?: boolean;
    defaultOpen?: boolean;
  }

  let { steps = [], isStreaming = false, defaultOpen = false }: Props = $props();

  let isOpen = $state(untrack(() => defaultOpen));

  // Auto-expand while streaming if steps are executing
  $effect(() => {
    if (isStreaming && steps.length > 0 && !isOpen) {
      isOpen = true;
    }
  });

  let runningStep = $derived(steps.find((s) => s.status === "running"));
  let completedCount = $derived(steps.filter((s) => s.status === "done").length);
</script>

{#if steps.length > 0}
  <div class="my-2 rounded-lg border border-border-subtle bg-surface-card/60 overflow-hidden text-xs transition-all">
    <button
      type="button"
      onclick={() => (isOpen = !isOpen)}
      class="w-full flex items-center justify-between px-3 py-2 text-left bg-surface-hover/40 hover:bg-surface-hover transition-colors font-medium text-fg-secondary"
      aria-expanded={isOpen}
    >
      <div class="flex items-center gap-2">
        <Brain class="w-4 h-4 text-accent animate-pulse" />
        <span class="font-semibold text-fg-primary">
          {runningStep ? runningStep.title : "Graph-RAG Reasoning Trace"}
        </span>
        <span class="text-[11px] font-mono text-fg-muted">
          ({completedCount}/{steps.length} steps)
        </span>
      </div>

      <div class="flex items-center gap-1.5 text-fg-muted">
        {#if runningStep}
          <span class="flex items-center gap-1 text-[11px] text-accent">
            <Loader2 class="w-3 h-3 animate-spin" />
            <span>Thinking...</span>
          </span>
        {/if}
        {#if isOpen}
          <ChevronDown class="w-4 h-4" />
        {:else}
          <ChevronRight class="w-4 h-4" />
        {/if}
      </div>
    </button>

    {#if isOpen}
      <div class="p-3 space-y-2.5 border-t border-border-subtle/60 bg-surface-canvas/40">
        {#each steps as step (step.step_index)}
          <div class="flex items-start gap-2.5 text-xs">
            <div class="mt-0.5 shrink-0">
              {#if step.status === "done"}
                <CheckCircle2 class="w-3.5 h-3.5 text-success" />
              {:else if step.status === "running"}
                <Loader2 class="w-3.5 h-3.5 text-accent animate-spin" />
              {:else if step.status === "failed"}
                <XCircle class="w-3.5 h-3.5 text-critical" />
              {:else}
                <div class="w-3.5 h-3.5 rounded-full border border-border-default bg-surface-card"></div>
              {/if}
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-2">
                <span class="font-medium text-fg-primary">{step.title}</span>
                <span class="text-[10px] font-mono text-fg-muted uppercase">
                  Step {step.step_index + 1}
                </span>
              </div>

              {#if step.description}
                <p class="text-[11px] text-fg-secondary leading-relaxed mt-0.5">
                  {step.description}
                </p>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}
