<!--
  ReliabilityLegend — the reference for the High / Medium / Low reliability grades.

  Two forms of the same reference, both opening the full explanation (the three
  tiers with examples, how they rank, what the grade is based on, and how bSDD
  fits in) from an "How reliability is graded" trigger:

    variant="key"     a one-line colour key next to the trigger, for the top of
                      a table so the pills below it read at a glance
    variant="trigger" just the trigger, for tight spots such as a form

  All wording comes from lib/reliability.ts, the same file the badge draws its
  colours from, so the reference and the grades can't drift apart.

  Usage:

      <ReliabilityLegend />
      <ReliabilityLegend variant="trigger" />
-->
<script lang="ts">
  import { Info } from "lucide-svelte";
  import HoverCard from "./HoverCard.svelte";
  import { cn } from "../utils/cn";
  import {
    RELIABILITY_BASIS_NOTE,
    RELIABILITY_BSDD_NOTE,
    RELIABILITY_SCALE_NOTE,
    RELIABILITY_STYLES,
    RELIABILITY_TIERS,
  } from "../reliability";

  interface Props {
    variant?: "key" | "trigger";
    class?: string;
  }

  let { variant = "key", class: className = "" }: Props = $props();
</script>

<div class={cn("flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-fg-muted", className)}>
  {#if variant === "key"}
    <span class="font-semibold uppercase tracking-wider">Reliability</span>
    {#each RELIABILITY_TIERS as tier (tier.level)}
      <span class="inline-flex items-center gap-1.5">
        <span class={cn("h-1.5 w-1.5 rounded-full", RELIABILITY_STYLES[tier.level].dot)}></span>
        <span class="font-semibold text-fg-secondary">{RELIABILITY_STYLES[tier.level].label}</span>
        <span>{tier.keyPhrase}</span>
      </span>
    {/each}
  {/if}

  <HoverCard
    side="bottom"
    align="start"
    width="w-96"
    title="Rule reliability"
    subtitle="How BIMGuard grades each rule"
  >
    {#snippet trigger()}
      <span class="inline-flex items-center gap-1 font-semibold text-accent hover:underline">
        <Info class="h-3.5 w-3.5" />
        How reliability is graded
      </span>
    {/snippet}

    <div class="space-y-3">
      {#each RELIABILITY_TIERS as tier (tier.level)}
        <div class="space-y-0.5">
          <div class="flex items-center gap-2">
            <span class={cn("h-2 w-2 rounded-full", RELIABILITY_STYLES[tier.level].dot)}></span>
            <span class="text-xs font-semibold text-fg-primary">{tier.title}</span>
          </div>
          <p class="text-xs text-fg-secondary">{tier.summary}</p>
          <p class="text-caption text-fg-muted">e.g. {tier.examples}</p>
        </div>
      {/each}

      <div class="space-y-1.5 border-t border-border-subtle pt-2.5">
        <p class="text-caption text-fg-secondary">{RELIABILITY_SCALE_NOTE}</p>
        <p class="text-caption text-fg-muted">{RELIABILITY_BASIS_NOTE}</p>
        <p class="text-caption text-fg-muted">{RELIABILITY_BSDD_NOTE}</p>
      </div>
    </div>
  </HoverCard>
</div>
