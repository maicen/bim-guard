<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
    children?: Snippet;
  }

  let { class: className, children }: Props = $props();
</script>

<div data-sidebar="group-content" class={cn("w-full text-sm", className)}>
  {@render children?.()}
</div>
