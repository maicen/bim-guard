<script lang="ts">
  import { FileCheck2, GitBranch, Workflow } from "lucide-svelte";
  import HoverCard from "./HoverCard.svelte";
  import {
    describeCdeState,
    describeRevision,
    describeSuitability,
  } from "../glossary";

  export let suitability: string = "S0";
  export let revision: string = "P01.01";
  export let cdeState: string = "WIP";
  export let size: "xs" | "sm" = "xs";

  function getCdeColor(state: string) {
    switch ((state || "").toUpperCase()) {
      case "PUBLISHED":
        return "text-emerald-400 border-emerald-800/60 bg-emerald-950/40";
      case "SHARED":
        return "text-blue-400 border-blue-800/60 bg-blue-950/40";
      case "ARCHIVED":
        return "text-slate-400 border-slate-700/60 bg-slate-900/60";
      default:
        return "text-amber-400 border-amber-800/60 bg-amber-950/40";
    }
  }

  // The badges are three-character codes in a dense table cell. The hover card
  // carries the meaning so the cell stays scannable but never cryptic.
  $: suitabilityCode = suitability || "S0";
  $: revisionCode = revision || "P01.01";
  $: cdeCode = cdeState || "WIP";
  $: suitabilityInfo = describeSuitability(suitabilityCode);
  $: revisionInfo = describeRevision(revisionCode);
  $: cdeInfo = describeCdeState(cdeCode);

  const CDE_ORDER = ["WIP", "SHARED", "PUBLISHED", "ARCHIVED"];
</script>

<div
  class="flex items-center gap-1.5 font-mono {size === 'xs'
    ? 'text-micro'
    : 'text-xs'}"
>
  <HoverCard
    side="top"
    align="start"
    width="w-80"
    icon={FileCheck2}
    title="{suitabilityCode} — {suitabilityInfo.label}"
    subtitle="ISO 19650 suitability status"
  >
    <span
      slot="trigger"
      class="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 font-semibold border border-slate-700/60 shadow-sm cursor-help"
    >
      {suitabilityCode}
    </span>

    {suitabilityInfo.description}

    <span slot="footer" class="font-mono">
      {suitabilityInfo.reference || "BS EN ISO 19650-2"}
    </span>
  </HoverCard>

  <HoverCard
    side="top"
    align="start"
    width="w-80"
    icon={GitBranch}
    title="{revisionCode} — {revisionInfo.label}"
    subtitle="ISO 19650 revision code"
  >
    <span
      slot="trigger"
      class="px-1.5 py-0.5 rounded bg-slate-800 text-blue-400 font-semibold border border-slate-700/60 shadow-sm cursor-help"
    >
      {revisionCode}
    </span>

    {revisionInfo.description}

    <span slot="footer" class="font-mono">
      {revisionInfo.reference || "BS EN ISO 19650-2"}
    </span>
  </HoverCard>

  <HoverCard
    side="top"
    align="end"
    width="w-80"
    icon={Workflow}
    title="{cdeCode} — {cdeInfo.label}"
    subtitle="Common data environment state"
  >
    <span
      slot="trigger"
      class="px-1.5 py-0.5 rounded font-semibold border shadow-sm cursor-help {getCdeColor(
        cdeCode,
      )}"
    >
      {cdeCode}
    </span>

    <p>{cdeInfo.description}</p>

    <!-- The state alone does not show how far along the container is; the
         ladder does, which is the question a reviewer actually has. -->
    <div class="flex items-center gap-1 mt-2 font-mono text-nano">
      {#each CDE_ORDER as state, i}
        {#if i > 0}
          <span class="text-slate-600">→</span>
        {/if}
        <span
          class="px-1.5 py-0.5 rounded border {state ===
          cdeCode.toUpperCase()
            ? 'bg-accent/15 border-accent/50 text-accent font-bold'
            : 'bg-slate-800/60 border-slate-700/50 text-slate-500'}"
        >
          {state}
        </span>
      {/each}
    </div>
  </HoverCard>
</div>
