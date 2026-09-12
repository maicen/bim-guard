<script lang="ts">
  import type { Component, ComponentType } from "svelte";
  import { Tabs } from "bits-ui";

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
  Generic tab strip built on bits-ui Tabs primitive for full WAI-ARIA
  keyboard navigation (Left/Right arrow keys, Home/End, focus roving).
-->
<Tabs.Root
  value={active}
  onValueChange={(val) => onSelect(val)}
  class="w-fit shrink-0"
>
  <Tabs.List
    class="flex w-fit items-center gap-1 rounded-xl border border-border-interactive bg-surface-overlay p-1"
    aria-label={ariaLabel}
  >
    {#each tabs as tab (tab.id)}
      <Tabs.Trigger
        value={tab.id}
        class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all duration-150 outline-hidden focus-visible:ring-2 focus-visible:ring-accent text-fg-muted hover:text-fg-primary data-[state=active]:bg-accent data-[state=active]:text-white shadow-none data-[state=active]:shadow-xs"
      >
        {#if tab.icon}
          <tab.icon class="h-3.5 w-3.5" />
        {/if}
        {tab.label}
      </Tabs.Trigger>
    {/each}
  </Tabs.List>
</Tabs.Root>
