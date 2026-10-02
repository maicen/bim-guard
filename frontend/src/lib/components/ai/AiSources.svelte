<!--
  AiSources — grounded citations list / carousel.
  Inspired by shadcn.io/ai/sources:
  Displays the full set of referenced document clauses and model elements
  grounding the assistant's answer, with click-through actions.
-->
<script lang="ts">
  import { FileText, Box, ShieldCheck, ExternalLink, ChevronDown, ChevronUp } from "lucide-svelte";
  import type { GraphRagCitation } from "../../types";

  interface Props {
    citations: GraphRagCitation[];
    onSelect?: (citation: GraphRagCitation) => void;
  }

  let { citations = [], onSelect }: Props = $props();

  let expanded = $state(false);
  let displayedCitations = $derived(expanded ? citations : citations.slice(0, 3));
</script>

{#if citations.length > 0}
  <div class="mt-3 pt-3 border-t border-border-subtle">
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-1.5 text-xs font-semibold text-fg-muted uppercase tracking-wider">
        <span>Grounded Sources</span>
        <span class="px-1.5 py-0.2 rounded-full bg-surface-hover text-fg-secondary text-[10px] font-mono">
          {citations.length}
        </span>
      </div>

      {#if citations.length > 3}
        <button
          type="button"
          onclick={() => expanded = !expanded}
          class="inline-flex items-center gap-1 text-xs text-accent hover:underline font-medium transition-colors"
        >
          <span>{expanded ? "Show less" : `+${citations.length - 3} more`}</span>
          {#if expanded}
            <ChevronUp class="w-3.5 h-3.5" />
          {:else}
            <ChevronDown class="w-3.5 h-3.5" />
          {/if}
        </button>
      {/if}
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
      {#each displayedCitations as citation, idx (citation.id + idx)}
        {@const isDoc = citation.source_type === "document"}
        {@const isModel = citation.source_type === "model"}
        
        <div
          class="flex flex-col justify-between p-2.5 rounded-lg border border-border-default bg-surface-card hover:bg-surface-hover hover:border-accent/40 transition-all text-xs group"
        >
          <div class="space-y-1">
            <div class="flex items-center justify-between gap-1 text-[11px]">
              <span class="inline-flex items-center gap-1 font-semibold {isDoc ? 'text-info' : isModel ? 'text-accent' : 'text-success'}">
                {#if isDoc}
                  <FileText class="w-3.5 h-3.5" />
                  <span>Document</span>
                {:else if isModel}
                  <Box class="w-3.5 h-3.5" />
                  <span>IFC Model</span>
                {:else}
                  <ShieldCheck class="w-3.5 h-3.5" />
                  <span>Rule</span>
                {/if}
              </span>

              <div class="flex items-center gap-1">
                {#if citation.retrieval_method}
                  <span class="px-1 py-0.2 rounded text-[9px] font-mono uppercase {citation.retrieval_method === 'hybrid_rrf' ? 'bg-accent/10 text-accent font-bold' : citation.retrieval_method === 'vector' ? 'bg-info/10 text-info' : 'bg-surface-hover text-fg-muted'}">
                    {citation.retrieval_method === 'hybrid_rrf' ? 'RRF' : citation.retrieval_method}
                  </span>
                {/if}

                {#if citation.page_number}
                  <span class="text-fg-muted font-mono text-[10px]">p. {citation.page_number}</span>
                {:else if citation.ifc_type}
                  <span class="text-fg-muted font-mono text-[10px] truncate max-w-[80px]">{citation.ifc_type}</span>
                {/if}
              </div>
            </div>

            <p class="font-medium text-fg-primary line-clamp-1 group-hover:text-accent transition-colors">
              {citation.title}
            </p>

            {#if citation.snippet}
              <p class="text-fg-secondary text-[11px] line-clamp-2 leading-relaxed">
                "{citation.snippet}"
              </p>
            {/if}
          </div>

          <div class="pt-2 mt-1 flex items-center justify-between border-t border-border-subtle/50 text-[10px] text-fg-muted">
            <span class="font-mono break-all select-all">
              {citation.element_guid || citation.reference}
            </span>

            {#if onSelect}
              <button
                type="button"
                onclick={() => onSelect(citation)}
                class="inline-flex items-center gap-0.5 text-accent hover:underline font-medium ml-auto"
              >
                <span>Inspect</span>
                <ExternalLink class="w-2.5 h-2.5" />
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}
