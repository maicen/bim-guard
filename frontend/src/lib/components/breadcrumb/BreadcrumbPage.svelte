<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    /** Whether this is the final, active crumb (adds aria-current="page"). Defaults to true. */
    current?: boolean;
    title?: string;
    class?: string;
    children: Snippet;
  }

  let {
    current = true,
    title,
    class: className = "font-semibold text-slate-100",
    children,
  }: Props = $props();
</script>

<span
  aria-current={current ? "page" : undefined}
  aria-disabled={current ? "true" : undefined}
  {title}
  class="min-w-0 {className}"
>
  {@render children()}
</span>
