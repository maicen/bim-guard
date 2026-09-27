<!--
  AiTool — tool execution card.
  Inspired by shadcn.io/ai/tool & ai/code-block:
  Displays an executed tool or Neo4j Cypher retrieval query, its status,
  and expandable parameters/query text.
-->
<script lang="ts">
  import { untrack } from "svelte";
  import { Terminal, Database, Check, Copy, ChevronDown, ChevronRight } from "lucide-svelte";
  import type { GraphRagToolCall } from "../../types";

  interface Props {
    toolCall: GraphRagToolCall;
    defaultExpanded?: boolean;
  }

  let { toolCall, defaultExpanded = false }: Props = $props();

  let expanded = $state(untrack(() => defaultExpanded));
  let copied = $state(false);

  function copyCode(text: string) {
    navigator.clipboard.writeText(text);
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }
</script>

<div class="my-2 rounded-lg border border-border-default bg-surface-card overflow-hidden text-xs">
  <div class="flex items-center justify-between px-3 py-2 bg-surface-hover/50 border-b border-border-subtle">
    <div class="flex items-center gap-2">
      {#if toolCall.cypher_query}
        <Database class="w-3.5 h-3.5 text-accent" />
      {:else}
        <Terminal class="w-3.5 h-3.5 text-info" />
      {/if}

      <span class="font-mono font-medium text-fg-primary">
        {toolCall.tool_name}
      </span>

      <span class="px-1.5 py-0.2 rounded text-[10px] font-mono {toolCall.status === 'success' ? 'bg-success-bg text-success' : toolCall.status === 'running' ? 'bg-accent/10 text-accent' : 'bg-critical-bg text-critical'}">
        {toolCall.status}
      </span>
    </div>

    <div class="flex items-center gap-2">
      {#if toolCall.output_summary}
        <span class="text-[11px] text-fg-muted truncate max-w-[200px]">
          {toolCall.output_summary}
        </span>
      {/if}

      <button
        type="button"
        onclick={() => (expanded = !expanded)}
        class="text-fg-muted hover:text-fg-primary p-0.5"
      >
        {#if expanded}
          <ChevronDown class="w-4 h-4" />
        {:else}
          <ChevronRight class="w-4 h-4" />
        {/if}
      </button>
    </div>
  </div>

  {#if expanded}
    <div class="p-3 space-y-2 bg-surface-canvas/60">
      {#if toolCall.cypher_query}
        <div class="space-y-1">
          <div class="flex items-center justify-between text-[11px] text-fg-muted font-mono">
            <span>Executed Cypher Query</span>
            <button
              type="button"
              onclick={() => copyCode(toolCall.cypher_query || "")}
              class="inline-flex items-center gap-1 text-accent hover:underline text-[10px]"
            >
              {#if copied}
                <Check class="w-3 h-3 text-success" />
                <span>Copied</span>
              {:else}
                <Copy class="w-3 h-3" />
                <span>Copy Cypher</span>
              {/if}
            </button>
          </div>
          <pre class="p-2.5 rounded bg-surface-card border border-border-subtle font-mono text-[11px] text-fg-secondary overflow-x-auto leading-relaxed">
            {toolCall.cypher_query}
          </pre>
        </div>
      {/if}

      {#if toolCall.arguments && Object.keys(toolCall.arguments).length > 0}
        <div class="space-y-1 text-[11px]">
          <span class="text-fg-muted font-mono">Arguments:</span>
          <pre class="p-2 rounded bg-surface-card border border-border-subtle font-mono text-[10px] text-fg-muted overflow-x-auto">
            {JSON.stringify(toolCall.arguments, null, 2)}
          </pre>
        </div>
      {/if}
    </div>
  {/if}
</div>
