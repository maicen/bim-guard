<script lang="ts">
  import { onMount, type Snippet } from "svelte";
  import {
    SidebarState,
    setSidebar,
    SIDEBAR_WIDTH,
    SIDEBAR_WIDTH_ICON,
    SIDEBAR_KEYBOARD_SHORTCUT,
  } from "./context.svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    defaultOpen?: boolean;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    class?: string;
    style?: string;
    children?: Snippet;
  }

  let {
    defaultOpen = true,
    open = $bindable(defaultOpen),
    onOpenChange,
    class: className,
    style,
    children,
  }: Props = $props();

  const sidebar = new SidebarState(open);
  setSidebar(sidebar);

  // Sync external open bindable with context
  $effect(() => {
    sidebar.open = open;
  });

  $effect(() => {
    if (sidebar.open !== open) {
      open = sidebar.open;
      onOpenChange?.(sidebar.open);
    }
  });

  onMount(() => {
    const mql = window.matchMedia("(max-width: 768px)");
    const updateIsMobile = () => {
      sidebar.isMobile = mql.matches;
    };
    updateIsMobile();
    mql.addEventListener("change", updateIsMobile);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key.toLowerCase() === SIDEBAR_KEYBOARD_SHORTCUT
      ) {
        event.preventDefault();
        sidebar.toggleSidebar();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      mql.removeEventListener("change", updateIsMobile);
      window.removeEventListener("keydown", handleKeyDown);
    };
  });
</script>

<div
  style="--sidebar-width: {SIDEBAR_WIDTH}; --sidebar-width-icon: {SIDEBAR_WIDTH_ICON}; {style || ''}"
  class={cn(
    "group/sidebar-wrapper flex min-h-svh w-full text-fg-primary has-data-[variant=inset]:bg-surface-canvas",
    className,
  )}
>
  {@render children?.()}
</div>
