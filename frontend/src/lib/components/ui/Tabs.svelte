<script lang="ts" module>
  import { Tabs as TabsPrimitive } from "bits-ui";

  export const TabsRoot = TabsPrimitive.Root;
  export const TabsList = TabsPrimitive.List;
  export const TabsTrigger = TabsPrimitive.Trigger;
  export const TabsContent = TabsPrimitive.Content;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    value?: string;
    onValueChange?: (value: string) => void;
    class?: string;
    children?: Snippet;
  }

  let {
    value = $bindable(""),
    onValueChange,
    class: className,
    children,
  }: Props = $props();
</script>

<TabsPrimitive.Root
  bind:value
  {onValueChange}
  class={cn("w-full space-y-4", className)}
>
  {@render children?.()}
</TabsPrimitive.Root>
