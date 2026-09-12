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
  class={cn(
    "rounded-xl border border-border-default bg-surface-card text-fg-primary shadow-xs transition-colors",
    className,
  )}
  {...rest}
>
  {@render children?.()}
</div>
