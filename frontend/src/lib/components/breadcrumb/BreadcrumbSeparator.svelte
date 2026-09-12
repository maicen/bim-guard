<script lang="ts">
  import type { Snippet } from "svelte";
  import { ChevronRight } from "lucide-svelte";

  interface Props {
    class?: string;
    children?: Snippet;
  }

  let { class: className = "", children }: Props = $props();
</script>

<li role="presentation" aria-hidden="true" class="inline-flex items-center {className}">
  {#if children}
    {@render children()}
  {:else}
    <ChevronRight class="h-3.5 w-3.5 text-slate-600" />
  {/if}
</li>
