<script lang="ts" module>
  import { cn } from "../../../utils/cn";

  export function navigationMenuTriggerStyle(className?: string): string {
    return cn(
      "group inline-flex h-9 w-max items-center justify-center rounded-lg bg-transparent px-3 py-2 text-xs font-medium text-fg-secondary transition-colors outline-hidden select-none hover:bg-surface-hover hover:text-fg-primary focus:bg-surface-hover focus:text-fg-primary focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 data-[state=open]:bg-surface-hover data-[state=open]:text-fg-primary",
      className,
    );
  }
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { NavigationMenu as NavigationMenuPrimitive } from "bits-ui";
  import { ChevronDown } from "lucide-svelte";

  let {
    ref = $bindable(null),
    class: className,
    children,
    ...restProps
  }: NavigationMenuPrimitive.TriggerProps & {
    children?: Snippet;
  } = $props();
</script>

<NavigationMenuPrimitive.Trigger
  bind:ref
  data-slot="navigation-menu-trigger"
  class={cn(navigationMenuTriggerStyle(), className)}
  {...restProps}
>
  {@render children?.()}
  <ChevronDown
    class="relative top-[1px] ml-1.5 h-3.5 w-3.5 text-fg-muted transition duration-200 group-data-[state=open]:rotate-180"
    aria-hidden="true"
  />
</NavigationMenuPrimitive.Trigger>
