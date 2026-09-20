<!--
  ReliabilityBadge — how reliably a rule can be checked against a real IFC model.

  High   : standard IFC attributes, geometry, quantities, relationships.
  Medium : standard property-set data (depends on correct authoring/export).
  Low    : custom, calculated or context-dependent data.

  The grade comes from the server (graded from the property the rule reads, not
  from the source document), so extracted and hand-written rules look the same.
  By default the reason opens in a hover card next to a compact pill (table
  cells); with `showReason` it is printed under the pill instead (forms, where
  the explanation has to be readable without hovering).

  Usage:

      <ReliabilityBadge reliability={draft.reliability} />
      <ReliabilityBadge reliability={grade} showReason fallback="Enter a property to grade it." />
-->
<script lang="ts">
  import HoverCard from "./HoverCard.svelte";
  import { cn } from "../utils/cn";
  import type { RuleReliability, RuleReliabilityLevel } from "../types";

  interface Props {
    reliability?: RuleReliability | null;
    /** Print the explanation under the pill instead of in a hover card. */
    showReason?: boolean;
    /** Rendered when there is nothing to grade (no property named). */
    fallback?: string;
    /** A new grade is being fetched; the previous one is dimmed meanwhile. */
    loading?: boolean;
  }

  let { reliability = null, showReason = false, fallback = "—", loading = false }: Props = $props();

  const STYLES: Record<RuleReliabilityLevel, { label: string; badge: string; dot: string }> = {
    high: {
      label: "High",
      badge: "bg-success-bg text-success border-success-border",
      dot: "bg-success",
    },
    medium: {
      label: "Medium",
      badge: "bg-caution-bg text-caution border-caution-border",
      dot: "bg-caution",
    },
    low: {
      label: "Low",
      badge: "bg-warning-bg text-warning border-warning-border",
      dot: "bg-warning",
    },
  };

  let style = $derived(reliability ? STYLES[reliability.level] : null);
</script>

{#snippet pill()}
  {#if style}
    <span
      class={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-micro font-semibold uppercase tracking-wider shadow-xs transition-opacity",
        style.badge,
        loading && "opacity-50",
      )}
    >
      <span class={cn("h-1.5 w-1.5 rounded-full", style.dot)}></span>
      <span>{style.label}</span>
    </span>
  {/if}
{/snippet}

{#if reliability && style}
  {#if showReason}
    <div class="space-y-1">
      {@render pill()}
      <p class="text-caption text-fg-muted">{reliability.reason}</p>
    </div>
  {:else}
    <HoverCard
      side="top"
      align="start"
      width="w-72"
      title={`${style.label} reliability`}
      subtitle="Graded from the IFC property this rule checks"
    >
      {#snippet trigger()}{@render pill()}{/snippet}
      <p class="text-xs text-fg-secondary">{reliability.reason}</p>
    </HoverCard>
  {/if}
{:else}
  <span class={cn("text-xs text-fg-muted", loading && "opacity-50")}>{loading ? "Grading…" : fallback}</span>
{/if}
