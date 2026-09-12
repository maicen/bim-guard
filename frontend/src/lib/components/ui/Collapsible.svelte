<script lang="ts" module>
  import { Collapsible as CollapsiblePrimitive } from "bits-ui";

  export const CollapsibleRoot = CollapsiblePrimitive.Root;
  export const CollapsibleTrigger = CollapsiblePrimitive.Trigger;
  export const CollapsibleContent = CollapsiblePrimitive.Content;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    disabled?: boolean;
    class?: string;
    children?: Snippet;
  }

  let {
    open = $bindable(false),
    onOpenChange,
    disabled = false,
    class: className,
    children,
  }: Props = $props();
</script>

<CollapsiblePrimitive.Root
  bind:open
  {onOpenChange}
  {disabled}
  class={cn("w-full", className)}
>
  {@render children?.()}
</CollapsiblePrimitive.Root>
