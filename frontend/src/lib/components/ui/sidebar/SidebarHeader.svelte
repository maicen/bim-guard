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
  data-sidebar="header"
  class={cn("flex flex-col gap-2 p-2 shrink-0 border-b border-border-default/40", className)}
>
  {@render children?.()}
</div>
