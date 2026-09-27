<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
    children?: Snippet;
  }

  let { class: className, children }: Props = $props();
</script>

<div
  data-sidebar="menu-badge"
  class={cn(
    "pointer-events-none absolute right-2 flex h-5 min-w-5 select-none items-center justify-center rounded-md px-1 text-nano font-medium tabular-nums text-fg-muted",
    "peer-hover/menu-button:text-fg-primary peer-data-[active=true]/menu-button:text-white",
    "group-data-[collapsible=icon]:hidden",
    className,
  )}
>
  {@render children?.()}
</div>
