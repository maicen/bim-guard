<script lang="ts">
  import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
  import { cn } from "../../../utils/cn";

  let {
    ref = $bindable(null),
    class: className,
    ...restProps
  }: NavigationMenuPrimitive.ViewportProps = $props();
</script>

<div class="absolute left-0 top-full flex justify-center w-full z-50">
  <NavigationMenuPrimitive.Viewport
    bind:ref
    data-slot="navigation-menu-viewport"
    class={cn(
      "origin-top-center relative mt-1.5 h-[var(--bits-navigation-menu-viewport-height)] w-full overflow-hidden rounded-xl border border-border-default bg-surface-card text-fg-primary shadow-2xl transition-[width,_height] duration-300 md:w-[var(--bits-navigation-menu-viewport-width)] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-90",
      className,
    )}
    {...restProps}
  />
</div>
