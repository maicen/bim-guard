<script lang="ts">
  import type { Snippet } from "svelte";
  import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
  import { cn } from "../../../utils/cn";

  let {
    ref = $bindable(null),
    class: className,
    children,
    ...restProps
  }: NavigationMenuPrimitive.ContentProps & {
    children?: Snippet;
  } = $props();
</script>

<NavigationMenuPrimitive.Content
  bind:ref
  data-slot="navigation-menu-content"
  class={cn(
    "left-0 top-0 w-full md:absolute",
    "data-[motion^=from-]:animate-in data-[motion^=to-]:animate-out data-[motion^=from-]:fade-in data-[motion^=to-]:fade-out data-[motion=from-end]:slide-in-from-right-52 data-[motion=from-start]:slide-in-from-left-52 data-[motion=to-end]:slide-out-to-right-52 data-[motion=to-start]:slide-out-to-left-52",
    "group-data-[viewport=false]/navigation-menu:bg-surface-card group-data-[viewport=false]/navigation-menu:text-fg-primary group-data-[viewport=false]/navigation-menu:data-[state=open]:animate-in group-data-[viewport=false]/navigation-menu:data-[state=closed]:animate-out group-data-[viewport=false]/navigation-menu:data-[state=closed]:zoom-out-95 group-data-[viewport=false]/navigation-menu:data-[state=open]:zoom-in-95 group-data-[viewport=false]/navigation-menu:data-[state=open]:fade-in-0 group-data-[viewport=false]/navigation-menu:data-[state=closed]:fade-out-0 group-data-[viewport=false]/navigation-menu:top-full group-data-[viewport=false]/navigation-menu:mt-2 group-data-[viewport=false]/navigation-menu:overflow-hidden group-data-[viewport=false]/navigation-menu:rounded-2xl group-data-[viewport=false]/navigation-menu:border group-data-[viewport=false]/navigation-menu:border-border-default group-data-[viewport=false]/navigation-menu:shadow-2xl group-data-[viewport=false]/navigation-menu:duration-200",
    className,
  )}
  {...restProps}
>
  {@render children?.()}
</NavigationMenuPrimitive.Content>
