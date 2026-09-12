<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";
  import { cn } from "../../utils/cn";

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: Snippet;
  }

  let { class: className, children, ...rest }: Props = $props();
</script>

<div
  class={cn("flex flex-col space-y-1.5 p-4 sm:p-5 border-b border-border-subtle", className)}
  {...rest}
>
  {@render children?.()}
</div>
