<script lang="ts" module>
  export {
    NavigationMenu,
    NavigationMenuRoot,
    Root,
    NavigationMenuList,
    NavigationMenuItem,
    NavigationMenuTrigger,
    navigationMenuTriggerStyle,
    NavigationMenuContent,
    NavigationMenuLink,
    NavigationMenuIndicator,
    NavigationMenuViewport,
    List,
    Item,
    Trigger,
    Content,
    Link,
    Indicator,
    Viewport,
  } from "./navigation-menu";
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import type { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
  import NavigationMenuRootComponent from "./navigation-menu/NavigationMenu.svelte";

  let {
    ref = $bindable(null),
    class: className,
    viewport = true,
    children,
    ...restProps
  }: NavigationMenuPrimitive.RootProps & {
    viewport?: boolean;
    children?: Snippet;
  } = $props();
</script>

<NavigationMenuRootComponent
  bind:ref
  class={className}
  {viewport}
  {...restProps}
>
  {@render children?.()}
</NavigationMenuRootComponent>
