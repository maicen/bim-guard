<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    class?: string;
    children?: Snippet;
  }

  let { class: className, children }: Props = $props();
</script>

<li data-sidebar="menu-sub-item" class={cn("group/menu-sub-item relative list-none", className)}>
  {@render children?.()}
</li>
