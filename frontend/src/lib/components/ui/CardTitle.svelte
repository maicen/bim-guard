<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";
  import { cn } from "../../utils/cn";

  interface Props extends HTMLAttributes<HTMLHeadingElement> {
    children?: Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<h3
  class={cn("text-sm font-semibold tracking-tight text-fg-primary leading-none", className)}
  {...rest}
>
  {@render children?.()}
</h3>
