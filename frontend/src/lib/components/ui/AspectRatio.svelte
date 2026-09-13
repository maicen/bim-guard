<script lang="ts" module>
  import { AspectRatio as AspectRatioPrimitive } from "bits-ui";

  export const AspectRatioRoot = AspectRatioPrimitive.Root;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    ratio?: number;
    class?: string;
    children?: Snippet;
  }

  let { ratio = 16 / 9, class: className, children }: Props = $props();
</script>

<AspectRatioPrimitive.Root {ratio} class={cn("relative w-full overflow-hidden", className)}>
  {@render children?.()}
</AspectRatioPrimitive.Root>
