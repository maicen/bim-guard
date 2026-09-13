<script lang="ts" module>
  import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";

  export const NavigationMenuRoot = NavigationMenuPrimitive.Root;
  export const NavigationMenuList = NavigationMenuPrimitive.List;
  export const NavigationMenuItem = NavigationMenuPrimitive.Item;
  export const NavigationMenuTrigger = NavigationMenuPrimitive.Trigger;
  export const NavigationMenuContent = NavigationMenuPrimitive.Content;
  export const NavigationMenuLink = NavigationMenuPrimitive.Link;
  export const NavigationMenuIndicator = NavigationMenuPrimitive.Indicator;
  export const NavigationMenuViewport = NavigationMenuPrimitive.Viewport;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    class?: string;
    children?: Snippet;
  }

  let { class: className, children }: Props = $props();
</script>

<NavigationMenuPrimitive.Root class={cn("relative z-10 flex max-w-max items-center justify-center", className)}>
  <NavigationMenuPrimitive.List class="group flex flex-1 list-none items-center justify-center gap-1">
    {@render children?.()}
  </NavigationMenuPrimitive.List>
  <div class="absolute left-0 top-full flex justify-center">
    <NavigationMenuPrimitive.Viewport class="relative mt-1.5 h-[var(--bits-navigation-menu-viewport-height)] w-full overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-2xl transition-[width,_height] duration-300 md:w-[var(--bits-navigation-menu-viewport-width)]" />
  </div>
</NavigationMenuPrimitive.Root>
