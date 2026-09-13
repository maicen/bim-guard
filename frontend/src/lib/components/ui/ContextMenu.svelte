<script lang="ts" module>
  import { ContextMenu as ContextMenuPrimitive } from "bits-ui";

  export const ContextMenuRoot = ContextMenuPrimitive.Root;
  export const ContextMenuTrigger = ContextMenuPrimitive.Trigger;
  export const ContextMenuPortal = ContextMenuPrimitive.Portal;
  export const ContextMenuContent = ContextMenuPrimitive.Content;
  export const ContextMenuItem = ContextMenuPrimitive.Item;
  export const ContextMenuGroup = ContextMenuPrimitive.Group;
  export const ContextMenuGroupHeading = ContextMenuPrimitive.GroupHeading;
  export const ContextMenuSeparator = ContextMenuPrimitive.Separator;
  export const ContextMenuSub = ContextMenuPrimitive.Sub;
  export const ContextMenuSubTrigger = ContextMenuPrimitive.SubTrigger;
  export const ContextMenuSubContent = ContextMenuPrimitive.SubContent;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    class?: string;
    trigger?: Snippet<[Record<string, any>]>;
    children?: Snippet;
  }

  let { class: className, trigger, children }: Props = $props();
</script>

<ContextMenuPrimitive.Root>
  {#if trigger}
    <ContextMenuPrimitive.Trigger>
      {#snippet child({ props })}
        {@render trigger({ ...props })}
      {/snippet}
    </ContextMenuPrimitive.Trigger>
  {/if}

  <ContextMenuPrimitive.Portal>
    <ContextMenuPrimitive.Content
      class={cn(
        "z-50 min-w-[160px] overflow-hidden rounded-2xl border border-border-default bg-surface-card p-1.5 shadow-2xl duration-150 animate-in fade-in zoom-in-95",
        className,
      )}
    >
      {@render children?.()}
    </ContextMenuPrimitive.Content>
  </ContextMenuPrimitive.Portal>
</ContextMenuPrimitive.Root>
