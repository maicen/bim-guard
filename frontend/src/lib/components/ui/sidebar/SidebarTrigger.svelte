<script lang="ts">
  import { PanelLeft } from "lucide-svelte";
  import { useSidebar } from "./context.svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
    onclick?: (e: MouseEvent) => void;
  }

  let { class: className, onclick }: Props = $props();

  const sidebar = useSidebar();

  function handleClick(e: MouseEvent) {
    onclick?.(e);
    if (!e.defaultPrevented) {
      sidebar.toggleSidebar();
    }
  }
</script>

<button
  type="button"
  data-sidebar="trigger"
  class={cn(
    "flex h-7 w-7 items-center justify-center rounded-md text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary focus-visible:ring-2 focus-visible:ring-accent outline-hidden",
    className,
  )}
  onclick={handleClick}
  aria-label="Toggle Sidebar"
  title="Toggle Sidebar"
>
  <PanelLeft class="h-4 w-4" />
</button>
