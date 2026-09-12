<script lang="ts">
  import type { Component, ComponentType } from "svelte";

  export interface TabStripItem {
    id: string;
    label: string;
    /** lucide-svelte still ships legacy ComponentType icons, so accept either. */
    icon?: Component<any> | ComponentType<any>;
  }

  interface Props {
    tabs: TabStripItem[];
    active: string;
    onSelect: (id: string) => void;
    ariaLabel?: string;
  }

  let { tabs, active, onSelect, ariaLabel = "Tabs" }: Props = $props();
</script>

<!--
  Generic tab strip — same visual treatment as AnalysisDomainTabs.svelte but
  driven by a `tabs` prop instead of a hardcoded 3-domain list, so any view
  that needs a simple switcher (e.g. External Providers' Document Parsing /
  LLM Providers panels) can reuse it instead of hand-rolling one.
-->
<div
  class="flex w-fit shrink-0 items-center gap-1 rounded-xl border border-border-interactive bg-surface-overlay p-1"
  role="tablist"
  aria-label={ariaLabel}
>
  {#each tabs as tab (tab.id)}
    <button
      type="button"
      role="tab"
      aria-selected={active === tab.id}
      onclick={() => onSelect(tab.id)}
      class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-colors {active ===
      tab.id
        ? 'bg-accent text-white'
        : 'text-fg-muted hover:text-white'}"
    >
      {#if tab.icon}
        <tab.icon class="h-3.5 w-3.5" />
      {/if}
      {tab.label}
    </button>
  {/each}
</div>
