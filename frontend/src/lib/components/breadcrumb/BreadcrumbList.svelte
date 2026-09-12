<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    class?: string;
    children: Snippet;
  }

  let { class: className = "", children }: Props = $props();
</script>

<ol
  class="flex min-w-0 flex-nowrap items-center gap-1.5 text-sm text-slate-500 sm:gap-2.5 {className}"
>
  {@render children()}
</ol>
