<script lang="ts">
  import type { Snippet } from "svelte";
  import { link } from "svelte-spa-router";
  import { cn } from "../../../utils/cn";

  interface Props {
    href?: string;
    isActive?: boolean;
    size?: "sm" | "md";
    class?: string;
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
  }

  let {
    href,
    isActive = false,
    size = "md",
    class: className,
    onclick,
    children,
  }: Props = $props();

  const buttonClasses = $derived(
    cn(
      "flex h-7 min-w-0 -translate-x-px items-center gap-2 overflow-hidden rounded-md px-2 text-fg-muted outline-hidden transition-colors hover:bg-surface-hover hover:text-fg-primary focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 select-none",
      size === "sm" && "text-caption",
      size === "md" && "text-xs",
      isActive && "bg-surface-hover text-fg-primary font-medium",
      className,
    )
  );
</script>

{#if href}
  <a
    {href}
    use:link
    data-sidebar="menu-sub-button"
    data-active={isActive}
    class={buttonClasses}
    {onclick}
  >
    {@render children?.()}
  </a>
{:else}
  <button
    type="button"
    data-sidebar="menu-sub-button"
    data-active={isActive}
    class={buttonClasses}
    {onclick}
  >
    {@render children?.()}
  </button>
{/if}
