<script lang="ts">
  import { useSidebar } from "./context.svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
  }

  let { class: className }: Props = $props();

  const sidebar = useSidebar();
</script>

<button
  type="button"
  data-sidebar="rail"
  aria-label="Toggle Sidebar"
  tabindex="-1"
  onclick={() => sidebar.toggleSidebar()}
  title="Toggle Sidebar"
  class={cn(
    "absolute inset-y-0 z-20 hidden w-4 -translate-x-1/2 transition-all ease-linear after:absolute after:inset-y-0 after:left-1/2 after:w-[2px] hover:after:bg-accent/50 group-data-[side=left]:-right-4 group-data-[side=right]:left-0 sm:flex outline-hidden",
    "[[data-side=left]_&]:cursor-w-resize [[data-side=right]_&]:cursor-e-resize",
    "[[data-side=left][data-state=collapsed]_&]:cursor-e-resize [[data-side=right][data-state=collapsed]_&]:cursor-w-resize",
    "group-data-[collapsible=offcanvas]:translate-x-0 group-data-[collapsible=offcanvas]:after:left-full group-data-[collapsible=offcanvas]:hover:bg-surface-canvas",
    "[[data-side=left][data-collapsible=offcanvas]_&]:-right-2",
    "[[data-side=right][data-collapsible=offcanvas]_&]:-left-2",
    className,
  )}
></button>
