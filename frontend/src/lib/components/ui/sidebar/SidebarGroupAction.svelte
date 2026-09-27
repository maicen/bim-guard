<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    title?: string;
    class?: string;
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
  }

  let { title, class: className, onclick, children }: Props = $props();
</script>

<button
  type="button"
  data-sidebar="group-action"
  {title}
  {onclick}
  class={cn(
    "absolute right-3 top-3.5 flex aspect-square w-5 items-center justify-center rounded-md p-0 text-fg-muted outline-hidden transition-transform hover:bg-surface-hover hover:text-fg-primary focus-visible:ring-2 focus-visible:ring-accent",
    "group-data-[collapsible=icon]:hidden",
    className,
  )}
>
  {@render children?.()}
</button>
