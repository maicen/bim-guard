<script lang="ts">
  import type { Snippet } from "svelte";
  import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
  import { cn } from "../../../utils/cn";

  let {
    ref = $bindable(null),
    class: className,
    children,
    ...restProps
  }: NavigationMenuPrimitive.LinkProps & {
    children?: Snippet;
  } = $props();
</script>

<NavigationMenuPrimitive.Link
  bind:ref
  data-slot="navigation-menu-link"
  class={cn(
    "flex flex-col gap-1 rounded-xl p-3 text-sm text-fg-secondary outline-hidden transition-colors hover:bg-surface-hover hover:text-fg-primary focus:bg-surface-hover focus:text-fg-primary focus-visible:ring-2 focus-visible:ring-accent data-[active=true]:bg-surface-selected data-[active=true]:text-fg-primary [&_svg:not([class*='text-'])]:text-fg-muted",
    className,
  )}
  {...restProps}
>
  {@render children?.()}
</NavigationMenuPrimitive.Link>
