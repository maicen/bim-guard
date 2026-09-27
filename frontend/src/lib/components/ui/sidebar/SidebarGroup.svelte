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
  data-sidebar="group"
  class={cn("relative flex w-full min-w-0 flex-col p-1.5", className)}
>
  {@render children?.()}
</div>
