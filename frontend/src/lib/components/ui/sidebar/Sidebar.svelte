<script lang="ts">
  import type { Snippet } from "svelte";
  import { useSidebar } from "./context.svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    side?: "left" | "right";
    variant?: "sidebar" | "floating" | "inset";
    collapsible?: "offcanvas" | "icon" | "none";
    class?: string;
    children?: Snippet;
  }

  let {
    side = "left",
    variant = "sidebar",
    collapsible = "offcanvas",
    class: className,
    children,
  }: Props = $props();

  const sidebar = useSidebar();
</script>

{#if collapsible === "none"}
  <div
    class={cn(
      "flex h-full w-(--sidebar-width) flex-col bg-surface-canvas border-r border-border-default text-fg-primary",
      className,
    )}
  >
    {@render children?.()}
  </div>
{:else if sidebar.isMobile}
  <!-- Mobile drawer sheet / scrim -->
  {#if sidebar.openMobile}
    <div
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs md:hidden animate-in fade-in-0 duration-200"
      onclick={() => sidebar.setOpenMobile(false)}
      onkeydown={(e) => e.key === "Escape" && sidebar.setOpenMobile(false)}
      role="button"
      tabindex="-1"
      aria-label="Close sidebar"
    ></div>
  {/if}

  <div
    data-sidebar="sidebar"
    data-mobile="true"
    class={cn(
      "fixed inset-y-0 z-50 flex h-full w-[calc(var(--sidebar-width)+2rem)] max-w-[85vw] flex-col bg-surface-canvas border-border-default text-fg-primary transition-transform duration-300 ease-in-out md:hidden shadow-2xl",
      side === "left"
        ? "left-0 border-r -translate-x-full data-[open=true]:translate-x-0"
        : "right-0 border-l translate-x-full data-[open=true]:translate-x-0",
      className,
    )}
    data-open={sidebar.openMobile}
  >
    <div class="flex h-full w-full flex-col">
      {@render children?.()}
    </div>
  </div>
{:else}
  <!-- Desktop Collapsible / Fixed Container -->
  <div
    class="group peer hidden md:block text-fg-primary"
    data-state={sidebar.state}
    data-collapsible={sidebar.state === "collapsed" ? collapsible : ""}
    data-variant={variant}
    data-side={side}
  >
    <!-- Spacer div that reserves width in the document flow -->
    <div
      class={cn(
        "duration-200 relative h-svh w-(--sidebar-width) bg-transparent transition-[width] ease-linear",
        "group-data-[collapsible=offcanvas]:w-0",
        "group-data-[side=right]:rotate-180",
        variant === "floating" || variant === "inset"
          ? "group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+theme(spacing.4))]"
          : "group-data-[collapsible=icon]:w-(--sidebar-width-icon)",
      )}
    ></div>

    <!-- The actual fixed sidebar panel -->
    <aside
      class={cn(
        "duration-200 fixed inset-y-0 z-20 hidden h-svh w-(--sidebar-width) transition-[left,right,width] ease-linear md:flex",
        side === "left"
          ? "left-0 group-data-[collapsible=offcanvas]:left-[calc(var(--sidebar-width)*-1)]"
          : "right-0 group-data-[collapsible=offcanvas]:right-[calc(var(--sidebar-width)*-1)]",
        // Adjust style based on variant
        variant === "floating"
          ? "p-2 group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+theme(spacing.4)+2px)]"
          : variant === "inset"
            ? "p-2 group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+theme(spacing.4)+2px)]"
            : "border-border-default group-data-[collapsible=icon]:w-(--sidebar-width-icon) group-data-[side=left]:border-r group-data-[side=right]:border-l",
        className,
      )}
    >
      <div
        data-sidebar="sidebar"
        class={cn(
          "flex h-full w-full flex-col bg-surface-canvas group-data-[variant=floating]:rounded-xl group-data-[variant=floating]:border group-data-[variant=floating]:border-border-default group-data-[variant=floating]:bg-surface-card group-data-[variant=floating]:shadow-lg",
        )}
      >
        {@render children?.()}
      </div>
    </aside>
  </div>
{/if}
