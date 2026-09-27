<script lang="ts">
  import { PanelLeft } from "lucide-svelte";
  import { useSidebar } from "./context.svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
    onclick?: (e: MouseEvent) => void;
  }

  let { class: className, onclick }: Props = $props();

  let sidebar: ReturnType<typeof useSidebar> | null = null;
  try {
    sidebar = useSidebar();
  } catch {
    sidebar = null;
  }

  function handleClick(e: MouseEvent) {
    onclick?.(e);
    if (!e.defaultPrevented && sidebar) {
      sidebar.toggleSidebar();
    }
  }
</script>

<button
  type="button"
  data-slot="sidebar-trigger"
  data-variant="ghost"
  data-size="icon"
  data-sidebar="trigger"
  class={cn(
    "inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-sm font-medium whitespace-nowrap transition-all outline-hidden focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 hover:bg-surface-hover hover:text-fg-primary text-fg-muted size-7 -ml-1 cursor-pointer",
    className,
  )}
  onclick={handleClick}
  aria-label="Toggle Sidebar"
  title="Toggle Sidebar"
>
  <PanelLeft class="lucide lucide-panel-left size-4" />
  <span class="sr-only">Toggle Sidebar</span>
</button>
