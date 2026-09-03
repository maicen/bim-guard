<script lang="ts">
  import { FileCheck2, GitBranch, Workflow } from "lucide-svelte";
  import HoverCard from "./HoverCard.svelte";
  import { describeCdeState, describeRevision, describeSuitability } from "../glossary";

  interface Props {
    suitability?: string;
    revision?: string;
    cdeState?: string;
    size?: "xs" | "sm";
  }

  let { suitability = "S0", revision = "P01.01", cdeState = "WIP", size = "xs" }: Props = $props();

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
  let suitabilityCode = $derived(suitability || "S0");
  let revisionCode = $derived(revision || "P01.01");
  let cdeCode = $derived(cdeState || "WIP");
  let suitabilityInfo = $derived(describeSuitability(suitabilityCode));
  let revisionInfo = $derived(describeRevision(revisionCode));
  let cdeInfo = $derived(describeCdeState(cdeCode));

  const CDE_ORDER = ["WIP", "SHARED", "PUBLISHED", "ARCHIVED"];
</script>

<div class="flex items-center gap-1.5 font-mono {size === 'xs' ? 'text-micro' : 'text-xs'}">
  <HoverCard
    side="top"
    align="start"
    width="w-80"
    icon={FileCheck2}
    title="{suitabilityCode} — {suitabilityInfo.label}"
    subtitle="ISO 19650 suitability status"
  >
    {#snippet trigger()}
      <span
        class="cursor-help rounded border border-slate-700/60 bg-slate-800 px-1.5 py-0.5 font-semibold text-amber-400 shadow-sm"
      >
        {suitabilityCode}
      </span>
    {/snippet}

    {suitabilityInfo.description}

    {#snippet footer()}
      <span class="font-mono">
        {suitabilityInfo.reference || "BS EN ISO 19650-2"}
      </span>
    {/snippet}
  </HoverCard>

  <HoverCard
    side="top"
    align="start"
    width="w-80"
    icon={GitBranch}
    title="{revisionCode} — {revisionInfo.label}"
    subtitle="ISO 19650 revision code"
  >
    {#snippet trigger()}
      <span
        class="cursor-help rounded border border-slate-700/60 bg-slate-800 px-1.5 py-0.5 font-semibold text-blue-400 shadow-sm"
      >
        {revisionCode}
      </span>
    {/snippet}

    {revisionInfo.description}

    {#snippet footer()}
      <span class="font-mono">
        {revisionInfo.reference || "BS EN ISO 19650-2"}
      </span>
    {/snippet}
  </HoverCard>

  <HoverCard
    side="top"
    align="end"
    width="w-80"
    icon={Workflow}
    title="{cdeCode} — {cdeInfo.label}"
    subtitle="Common data environment state"
  >
    {#snippet trigger()}
      <span
        class="cursor-help rounded border px-1.5 py-0.5 font-semibold shadow-sm {getCdeColor(
          cdeCode,
        )}"
      >
        {cdeCode}
      </span>
    {/snippet}

    <p>{cdeInfo.description}</p>

    <!-- The state alone does not show how far along the container is; the
         ladder does, which is the question a reviewer actually has. -->
    <div class="mt-2 flex items-center gap-1 font-mono text-nano">
      {#each CDE_ORDER as state, i (state)}
        {#if i > 0}
          <span class="text-slate-600">→</span>
        {/if}
        <span
          class="rounded border px-1.5 py-0.5 {state === cdeCode.toUpperCase()
            ? 'border-accent/50 bg-accent/15 font-bold text-accent'
            : 'border-slate-700/50 bg-slate-800/60 text-slate-500'}"
        >
          {state}
        </span>
      {/each}
    </div>
  </HoverCard>
</div>
