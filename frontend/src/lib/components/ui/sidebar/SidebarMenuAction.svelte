<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    showOnHover?: boolean;
    class?: string;
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
  }

  let {
    showOnHover = false,
    class: className,
    onclick,
    children,
  }: Props = $props();
</script>

<button
  type="button"
  data-sidebar="menu-action"
  {onclick}
  class={cn(
    "absolute right-1 top-1.5 flex aspect-square w-5 items-center justify-center rounded-md p-0 text-fg-muted outline-hidden transition-transform hover:bg-surface-hover hover:text-fg-primary focus-visible:ring-2 focus-visible:ring-accent",
    "group-data-[collapsible=icon]:hidden",
    showOnHover &&
      "peer-data-[active=true]/menu-button:text-fg-primary group-focus-within/menu-item:opacity-100 group-hover/menu-item:opacity-100 md:opacity-0",
    className,
  )}
>
  {@render children?.()}
</button>
