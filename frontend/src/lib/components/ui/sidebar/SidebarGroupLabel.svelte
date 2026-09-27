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
  data-sidebar="group-label"
  class={cn(
    "duration-200 flex h-7 shrink-0 items-center rounded-md px-2 text-nano font-bold uppercase tracking-wider text-fg-muted outline-hidden transition-[margin,opacity] ease-linear select-none",
    "group-data-[collapsible=icon]:-mt-7 group-data-[collapsible=icon]:opacity-0 pointer-events-none group-data-[collapsible=icon]:pointer-events-none",
    className,
  )}
>
  {@render children?.()}
</div>
