<script lang="ts">
  import { LayoutList, Cpu, Compass } from "lucide-svelte";

  export type AnalysisDomainTab = "arch" | "piping" | "seismic";

  interface Props {
    active: AnalysisDomainTab;
    onSelect: (domain: AnalysisDomainTab) => void;
  }

  let { active, onSelect }: Props = $props();

  const TABS: { id: AnalysisDomainTab; label: string; icon: typeof LayoutList }[] = [
    { id: "arch", label: "Architectural", icon: LayoutList },
    { id: "piping", label: "Piping", icon: Cpu },
    { id: "seismic", label: "Seismic", icon: Compass },
  ];
</script>

<!--
  A single "Compliance Audit" sidebar destination now covers all three
  domains — this tab strip is how you switch between them without going
  back to the sidebar, mirroring the Compliance/ISO toggle already used
  inside the Architectural view itself.
-->
<div
  class="flex w-fit shrink-0 items-center gap-1 rounded-xl border border-slate-700 bg-slate-800/40 p-1"
  role="tablist"
  aria-label="Analysis domain"
>
  {#each TABS as tab (tab.id)}
    <button
      type="button"
      role="tab"
      aria-selected={active === tab.id}
      onclick={() => onSelect(tab.id)}
      class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-colors {active ===
      tab.id
        ? 'bg-accent text-white'
        : 'text-slate-400 hover:text-white'}"
    >
      <tab.icon class="h-3.5 w-3.5" />
      {tab.label}
    </button>
  {/each}
</div>
