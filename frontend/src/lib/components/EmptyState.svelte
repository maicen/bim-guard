<script lang="ts">
  import type { ComponentType } from "svelte";
  import { SearchX } from "lucide-svelte";

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
  class="space-y-3 rounded-2xl border border-dashed border-slate-800 p-12 text-center text-xs text-slate-500 duration-200 animate-in fade-in"
>
  <div
    class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900 text-slate-400"
  >
    {#if icon}
      {@const SvelteComponent = icon}
      <SvelteComponent class="h-6 w-6" />
    {:else}
      <SearchX class="h-6 w-6 text-slate-500" />
    {/if}
  </div>

  <div class="space-y-1">
    <div class="text-sm font-bold text-slate-50">{title}</div>
    {#if description}
      <div class="mx-auto max-w-sm text-xs leading-relaxed text-slate-400">
        {description}
      </div>
    {/if}
  </div>

  {@render children?.()}

  {#if actionLabel && onAction}
    <div class="pt-1">
      <button
        type="button"
        onclick={onAction}
        class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
      >
        <span>{actionLabel}</span>
      </button>
    </div>
  {/if}
</div>
