<script lang="ts">
  import type { ComponentType } from "svelte";

  export let category: string = "";
  export let title: string = "";
  export let subtitle: string = "";
  export let icon: ComponentType | null = null;
</script>

<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
  <div>
    {#if category}
      <div class="text-xs font-bold uppercase tracking-widest text-accent mb-1 flex items-center gap-1.5">
        <span>{category}</span>
        <slot name="category-extra" />
      </div>
    {/if}

    <div class="flex items-center gap-3 flex-wrap">
      {#if icon}
        <svelte:component this={icon} class="w-6 h-6 text-accent shrink-0" />
      {/if}
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50 flex items-center gap-2.5">
        <span>{title}</span>
        <slot name="badge" />
      </h1>
    </div>

    {#if subtitle}
      <p class="text-xs sm:text-sm text-slate-400 mt-1 max-w-3xl leading-relaxed">
        {subtitle}
      </p>
    {/if}
  </div>

  {#if $$slots.actions}
    <div class="flex items-center gap-2.5 shrink-0 flex-wrap">
      <slot name="actions" />
    </div>
  {/if}
</div>
