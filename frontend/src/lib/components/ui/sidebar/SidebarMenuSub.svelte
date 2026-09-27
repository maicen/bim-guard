<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
    children?: Snippet;
  }

  let { class: className, children }: Props = $props();
</script>

<ul
  data-sidebar="menu-sub"
  class={cn(
    "mx-3.5 flex min-w-0 translate-x-px flex-col gap-1 border-l border-border-default px-2.5 py-0.5 list-none m-0",
    "group-data-[collapsible=icon]:hidden",
    className,
  )}
>
  {@render children?.()}
</ul>
