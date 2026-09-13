<script lang="ts" module>
  import { ScrollArea as ScrollAreaPrimitive } from "bits-ui";

  export const ScrollAreaRoot = ScrollAreaPrimitive.Root;
  export const ScrollAreaViewport = ScrollAreaPrimitive.Viewport;
  export const ScrollAreaScrollbar = ScrollAreaPrimitive.Scrollbar;
  export const ScrollAreaThumb = ScrollAreaPrimitive.Thumb;
  export const ScrollAreaCorner = ScrollAreaPrimitive.Corner;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    type?: "auto" | "always" | "scroll" | "hover";
    dir?: "ltr" | "rtl";
    orientation?: "vertical" | "horizontal" | "both";
    class?: string;
    viewportClass?: string;
    children?: Snippet;
  }

  let {
    type = "hover",
    dir = "ltr",
    orientation = "vertical",
    class: className,
    viewportClass,
    children,
  }: Props = $props();
</script>

<ScrollAreaPrimitive.Root
  {type}
  {dir}
  class={cn("relative overflow-hidden", className)}
>
  <ScrollAreaPrimitive.Viewport class={cn("h-full w-full rounded-[inherit]", viewportClass)}>
    {@render children?.()}
  </ScrollAreaPrimitive.Viewport>

  {#if orientation === "vertical" || orientation === "both"}
    <ScrollAreaPrimitive.Scrollbar
      orientation="vertical"
      class="flex select-none touch-none p-0.5 transition-colors duration-150 ease-out hover:bg-surface-canvas/20 data-[orientation=vertical]:w-2"
    >
      <ScrollAreaPrimitive.Thumb class="relative flex-1 rounded-full bg-border-interactive/60 hover:bg-border-interactive" />
    </ScrollAreaPrimitive.Scrollbar>
  {/if}

  {#if orientation === "horizontal" || orientation === "both"}
    <ScrollAreaPrimitive.Scrollbar
      orientation="horizontal"
      class="flex select-none touch-none p-0.5 transition-colors duration-150 ease-out hover:bg-surface-canvas/20 data-[orientation=horizontal]:h-2"
    >
      <ScrollAreaPrimitive.Thumb class="relative flex-1 rounded-full bg-border-interactive/60 hover:bg-border-interactive" />
    </ScrollAreaPrimitive.Scrollbar>
  {/if}

  <ScrollAreaPrimitive.Corner />
</ScrollAreaPrimitive.Root>
