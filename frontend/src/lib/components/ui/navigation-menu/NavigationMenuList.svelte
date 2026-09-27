<script lang="ts">
  import type { Snippet } from "svelte";
  import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
  import { cn } from "../../../utils/cn";

  let {
    ref = $bindable(null),
    class: className,
    children,
    ...restProps
  }: NavigationMenuPrimitive.ListProps & {
    children?: Snippet;
  } = $props();
</script>

<NavigationMenuPrimitive.List
  bind:ref
  data-slot="navigation-menu-list"
  class={cn("group flex flex-1 list-none items-center justify-center gap-1", className)}
  {...restProps}
>
  {@render children?.()}
</NavigationMenuPrimitive.List>
