<script lang="ts">
  import type { ComponentType } from "svelte";
  import { SearchX } from "lucide-svelte";
  import Button from "./ui/Button.svelte";

  interface Props {
    title?: string;
    description?: string;
    icon?: ComponentType | null;
    actionLabel?: string;
    onAction?: (() => void) | null;
    children?: import("svelte").Snippet;
  }

  let {
    title = "No items found",
    description = "",
    icon = null,
    actionLabel = "",
    onAction = null,
    children,
  }: Props = $props();
</script>

<div
  class="space-y-3 rounded-2xl border border-dashed border-border-default p-12 text-center text-xs text-fg-muted duration-200 animate-in fade-in"
>
  <div
    class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-border-default bg-surface-card text-fg-muted"
  >
    {#if icon}
      {@const SvelteComponent = icon}
      <SvelteComponent class="h-6 w-6" />
    {:else}
      <SearchX class="h-6 w-6" />
    {/if}
  </div>

  <div class="space-y-1">
    <div class="text-sm font-bold text-fg-primary">{title}</div>
    {#if description}
      <div class="mx-auto max-w-sm text-xs leading-relaxed text-fg-secondary">
        {description}
      </div>
    {/if}
  </div>

  {@render children?.()}

  {#if actionLabel && onAction}
    <div class="pt-1">
      <Button variant="primary" size="md" onclick={onAction}>
        {actionLabel}
      </Button>
    </div>
  {/if}
</div>
