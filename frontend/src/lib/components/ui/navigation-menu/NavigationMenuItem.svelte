<script lang="ts">
  import type { Snippet } from "svelte";
  import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
  import { cn } from "../../../utils/cn";

  let {
    ref = $bindable(null),
    class: className,
    children,
    ...restProps
  }: NavigationMenuPrimitive.ItemProps & {
    children?: Snippet;
  } = $props();
</script>

<NavigationMenuPrimitive.Item
  bind:ref
  data-slot="navigation-menu-item"
  class={cn("relative", className)}
  {...restProps}
>
  {@render children?.()}
</NavigationMenuPrimitive.Item>
