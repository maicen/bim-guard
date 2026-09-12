<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    class?: string;
    children: Snippet;
  }

  let { class: className = "", children }: Props = $props();
</script>

<li class="inline-flex min-w-0 items-center gap-1.5 {className}">
  {@render children()}
</li>
