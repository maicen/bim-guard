<script lang="ts">
  import type { ComponentType } from 'svelte';

  export let title: string;
  export let value: string | number | null = null;
  export let description: string | null = null;
  export let dark: boolean = false;
  export let icon: ComponentType | null = null;
  export let trend: string | null = null;
  export let trendUp: boolean | null = null;
  export let cls: string = '';
</script>

<div
  class="rounded-[1.75rem] border transition-all duration-300 hover:scale-[1.01] p-6 flex flex-col justify-between {dark
    ? 'bg-slate-900/90 border-slate-700 text-white shadow-xl shadow-black/40'
    : 'bg-slate-900/50 border-slate-800/80 text-slate-100'} {cls}"
>
  <div class="flex items-start justify-between gap-3">
    <div class="space-y-1.5">
      <p class="text-[11px] font-bold uppercase tracking-widest text-slate-400">
        {title}
      </p>
      {#if value !== null}
        <h3 class="text-3xl font-extrabold tracking-tight {dark ? 'text-white' : 'text-slate-100'}">
          {value}
        </h3>
      {/if}
    </div>

    {#if icon}
      <div class="w-10 h-10 rounded-2xl flex items-center justify-center {dark ? 'bg-white/10 text-white' : 'bg-slate-800 text-slate-400'} shrink-0">
        <svelte:component this={icon} class="w-5 h-5" />
      </div>
    {/if}
  </div>

  {#if $$slots.default}
    <div class="mt-4">
      <slot />
    </div>
  {/if}

  {#if description || trend}
    <div class="mt-4 flex items-center gap-2 text-xs">
      {#if trend}
        <span
          class="font-semibold px-2 py-0.5 rounded-full {trendUp === true
            ? 'bg-emerald-950/80 border border-emerald-800 text-emerald-400'
            : trendUp === false
            ? 'bg-rose-950/80 border border-rose-800 text-rose-400'
            : 'bg-slate-800 text-slate-300'}"
        >
          {trend}
        </span>
      {/if}
      {#if description}
        <p class="text-slate-400 truncate">
          {description}
        </p>
      {/if}
    </div>
  {/if}
</div>
