<script lang="ts" module>
  import { Accordion as AccordionPrimitive } from "bits-ui";

  export const AccordionRoot = AccordionPrimitive.Root;
  export const AccordionItem = AccordionPrimitive.Item;
  export const AccordionHeader = AccordionPrimitive.Header;
  export const AccordionTrigger = AccordionPrimitive.Trigger;
  export const AccordionContent = AccordionPrimitive.Content;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    type?: "single" | "multiple";
    value?: string | string[];
    class?: string;
    children?: Snippet;
  }

  let {
    type = "single",
    value = $bindable(),
    class: className,
    children,
  }: Props = $props();
</script>

<!-- svelte-ignore state_referenced_locally -->
<AccordionPrimitive.Root
  {type}
  bind:value={value as any}
  class={cn("w-full divide-y divide-border-subtle rounded-xl border border-border-default bg-surface-card", className)}
>
  {@render children?.()}
</AccordionPrimitive.Root>
