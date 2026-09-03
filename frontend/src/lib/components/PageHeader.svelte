<script lang="ts">
  import type { Component, ComponentType, Snippet } from "svelte";

  let {
    category = "",
    title = "",
    subtitle = "",
    icon = null,
    categoryExtra,
    badge,
    actions,
  }: {
    category?: string;
    title?: string;
    subtitle?: string;
    /** lucide-svelte still ships legacy ComponentType icons, so accept either. */
    icon?: Component<any> | ComponentType<any> | null;
    categoryExtra?: Snippet;
    badge?: Snippet;
    actions?: Snippet;
  } = $props();

  const Icon = $derived(icon);
</script>

<div class="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
  <div>
    {#if category}
      <div
        class="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-accent"
      >
        <span>{category}</span>
        {@render categoryExtra?.()}
      </div>
    {/if}

    <div class="flex flex-wrap items-center gap-3">
      {#if Icon}
        <Icon class="h-6 w-6 shrink-0 text-accent" />
      {/if}
      <h1
        class="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl"
      >
        <span>{title}</span>
        {@render badge?.()}
      </h1>
    </div>

    {#if subtitle}
      <p class="mt-1 max-w-3xl text-xs leading-relaxed text-slate-400 sm:text-sm">
        {subtitle}
      </p>
    {/if}
  </div>

  {#if actions}
    <div class="flex shrink-0 flex-wrap items-center gap-2.5">
      {@render actions()}
    </div>
  {/if}
</div>
