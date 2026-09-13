<script lang="ts" module>
  import { Label as LabelPrimitive } from "bits-ui";

  export const LabelRoot = LabelPrimitive.Root;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    for?: string;
    required?: boolean;
    class?: string;
    children?: Snippet;
  }

  let { for: htmlFor, required = false, class: className, children }: Props = $props();
</script>

<LabelPrimitive.Root
  for={htmlFor}
  class={cn(
    "text-caption font-semibold text-fg-secondary select-none cursor-pointer",
    className,
  )}
>
  {@render children?.()}
  {#if required}
    <span class="text-critical ml-0.5" aria-hidden="true">*</span>
  {/if}
</LabelPrimitive.Root>
