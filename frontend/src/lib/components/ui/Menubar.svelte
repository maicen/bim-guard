<script lang="ts" module>
  import { Menubar as MenubarPrimitive } from "bits-ui";

  export const MenubarRoot = MenubarPrimitive.Root;
  export const MenubarMenu = MenubarPrimitive.Menu;
  export const MenubarTrigger = MenubarPrimitive.Trigger;
  export const MenubarPortal = MenubarPrimitive.Portal;
  export const MenubarContent = MenubarPrimitive.Content;
  export const MenubarItem = MenubarPrimitive.Item;
  export const MenubarSeparator = MenubarPrimitive.Separator;
  export const MenubarGroup = MenubarPrimitive.Group;
  export const MenubarGroupHeading = MenubarPrimitive.GroupHeading;
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

<MenubarPrimitive.Root
  class={cn(
    "flex items-center gap-1 rounded-xl border border-border-default bg-surface-card p-1 shadow-xs",
    className,
  )}
>
  {@render children?.()}
</MenubarPrimitive.Root>
