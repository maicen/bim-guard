<!--
  AiLoader — shimmer & streaming pulse.
  Inspired by shadcn.io/ai/loader & ai/shimmer:
  Prevents layout shifts while Graph-RAG queries Neo4j and synthesizes answers.
-->
<script lang="ts">
  import { Sparkles, Brain } from "lucide-svelte";

  interface Props {
    statusText?: string;
  }

  let { statusText = "Graph-RAG is querying Neo4j knowledge graph..." }: Props = $props();
</script>

<div class="my-3 p-4 rounded-xl border border-border-subtle bg-surface-card/70 space-y-3">
  <div class="flex items-center gap-2 text-xs font-medium text-accent">
    <Brain class="w-4 h-4 animate-bounce" />
    <span class="animate-pulse">{statusText}</span>
    <Sparkles class="w-3.5 h-3.5 text-accent/60 animate-spin" />
  </div>

  <div class="space-y-2 animate-pulse">
    <div class="h-3 bg-surface-hover rounded w-3/4"></div>
    <div class="h-3 bg-surface-hover rounded w-5/6"></div>
    <div class="h-3 bg-surface-hover rounded w-1/2"></div>
  </div>
</div>
