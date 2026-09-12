<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    href?: string;
    onclick?: () => void;
    title?: string;
    class?: string;
    children: Snippet;
  }

  let { href, onclick, title, class: className = "", children }: Props = $props();
</script>

{#if href}
  <a
    {href}
    {title}
    class="font-medium text-fg-muted transition-colors hover:text-fg-primary {className}"
  >
    {@render children()}
  </a>
{:else}
  <button
    type="button"
    {onclick}
    {title}
    class="font-medium text-fg-muted transition-colors hover:text-fg-primary {className}"
  >
    {@render children()}
  </button>
{/if}
