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
  data-sidebar="menu"
  class={cn("flex w-full min-w-0 flex-col gap-1 list-none p-0 m-0", className)}
>
  {@render children?.()}
</ul>
