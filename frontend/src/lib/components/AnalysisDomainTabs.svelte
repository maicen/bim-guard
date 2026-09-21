<script lang="ts">
  import { LayoutList } from "lucide-svelte";

  export type AnalysisDomainTab = "arch";

  interface Props {
    active: AnalysisDomainTab;
    onSelect: (domain: AnalysisDomainTab) => void;
    /** Restrict the strip to a project's own domain. Arch is the only domain today. */
    allowedDomains?: AnalysisDomainTab[];
  }

  let { active, onSelect, allowedDomains }: Props = $props();

  const ALL_TABS: { id: AnalysisDomainTab; label: string; icon: typeof LayoutList }[] = [
    { id: "arch", label: "Architectural", icon: LayoutList },
  ];

  let TABS = $derived(
    allowedDomains ? ALL_TABS.filter((tab) => allowedDomains.includes(tab.id)) : ALL_TABS,
  );
</script>

<!--
  A single "Compliance Audit" sidebar destination covers the Architectural
  domain -- the only one BIM-Guard analyses today.
-->
<div
  class="flex w-fit shrink-0 items-center gap-1 rounded-xl border border-border-interactive bg-surface-overlay p-1"
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
        ? 'bg-blue-600 text-white shadow-xs'
        : 'text-fg-muted hover:text-white'}"
    >
      <tab.icon class="h-3.5 w-3.5" />
      {tab.label}
    </button>
  {/each}
</div>
