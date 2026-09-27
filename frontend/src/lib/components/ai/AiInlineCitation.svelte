<!--
  AiInlineCitation — grounded inline reference pill.
  Inspired by shadcn.io/ai/inline-citation:
  Renders an interactive citation badge [Doc: ...] or [IFC: ...] with a rich
  HoverCard preview showing clause text or model element property sets.
-->
<script lang="ts">
  import { FileText, Box, ShieldCheck, ExternalLink } from "lucide-svelte";
  import HoverCard from "../HoverCard.svelte";
  import type { GraphRagCitation } from "../../types";

  interface Props {
    citation: GraphRagCitation;
    index?: number;
    onSelect?: (citation: GraphRagCitation) => void;
  }

  let { citation, index, onSelect }: Props = $props();

  let isDoc = $derived(citation.source_type === "document");
  let isModel = $derived(citation.source_type === "model");
  let icon = $derived(isDoc ? FileText : isModel ? Box : ShieldCheck);
</script>

<span class="inline-block align-baseline mx-0.5">
  <HoverCard
    side="top"
    align="center"
    title={citation.title}
    subtitle={citation.reference}
    icon={icon}
    width="w-80"
  >
    {#snippet trigger()}
      <button
        type="button"
        onclick={() => onSelect?.(citation)}
        class="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-mono font-medium rounded-md transition-all
               border border-border-default hover:border-accent hover:text-accent
               {isDoc ? 'bg-info-bg text-info' : isModel ? 'bg-accent/10 text-accent' : 'bg-success-bg text-success'}"
        title="Inspect grounded evidence"
      >
        <span class="text-[10px] font-sans font-semibold uppercase opacity-75">
          {isDoc ? "Doc" : isModel ? "IFC" : "Rule"}
        </span>
        {#if index !== undefined}
          <span class="text-[11px] font-bold">[{index + 1}]</span>
        {:else}
          <span class="truncate max-w-[120px]">{citation.reference}</span>
        {/if}
      </button>
    {/snippet}

    <div class="space-y-2 text-xs">
      {#if citation.snippet}
        <p class="text-fg-secondary leading-relaxed line-clamp-4">
          "{citation.snippet}"
        </p>
      {/if}

      <div class="flex flex-wrap gap-1.5 pt-1 text-[11px] text-fg-muted font-mono">
        {#if citation.page_number}
          <span class="px-1.5 py-0.5 rounded bg-surface-canvas border border-border-subtle">
            Page {citation.page_number}
          </span>
        {/if}
        {#if citation.element_guid}
          <span class="px-1.5 py-0.5 rounded bg-surface-canvas border border-border-subtle truncate max-w-[160px]">
            GUID: {citation.element_guid}
          </span>
        {/if}
        {#if citation.ifc_type}
          <span class="px-1.5 py-0.5 rounded bg-surface-canvas border border-border-subtle">
            {citation.ifc_type}
          </span>
        {/if}
        {#if citation.properties?.fire_rating}
          <span class="px-1.5 py-0.5 rounded bg-caution-bg text-caution border border-caution-border">
            Rating: {citation.properties.fire_rating}
          </span>
        {/if}
      </div>

      {#if onSelect}
        <button
          type="button"
          onclick={() => onSelect?.(citation)}
          class="inline-flex items-center gap-1 text-accent hover:underline font-medium pt-1"
        >
          <span>{isDoc ? "View in Document Viewer" : "Isolate in 3D BIM Viewer"}</span>
          <ExternalLink class="w-3 h-3" />
        </button>
      {/if}
    </div>
  </HoverCard>
</span>
