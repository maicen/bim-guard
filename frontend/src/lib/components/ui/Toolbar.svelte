<script lang="ts" module>
  import { Toolbar as ToolbarPrimitive } from "bits-ui";

  export const ToolbarRoot = ToolbarPrimitive.Root;
  export const ToolbarButton = ToolbarPrimitive.Button;
  export const ToolbarLink = ToolbarPrimitive.Link;
  export const ToolbarGroup = ToolbarPrimitive.Group;
  export const ToolbarGroupItem = ToolbarPrimitive.GroupItem;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    orientation?: "horizontal" | "vertical";
    loop?: boolean;
    class?: string;
    children?: Snippet;
  }

  let {
    orientation = "horizontal",
    loop = true,
    class: className,
    children,
  }: Props = $props();
</script>

<ToolbarPrimitive.Root
  {orientation}
  {loop}
  class={cn(
    "flex items-center gap-1 rounded-xl border border-border-default bg-surface-card p-1.5 shadow-xs",
    orientation === "vertical" ? "flex-col" : "flex-row",
    className,
  )}
>
  {@render children?.()}
</ToolbarPrimitive.Root>
