<script lang="ts">
  import type { ComponentType } from "svelte";

  interface Props {
    title: string;
    value?: string | number | null;
    description?: string | null;
    dark?: boolean;
    icon?: ComponentType | null;
    trend?: string | null;
    trendUp?: boolean | null;
    cls?: string;
    children?: import("svelte").Snippet;
  }

  let {
    title,
    value = null,
    description = null,
    dark = false,
    icon = null,
    trend = null,
    trendUp = null,
    cls = "",
    children,
  }: Props = $props();
</script>

<div
  class="flex flex-col justify-between rounded-[1.75rem] border p-6 transition-all duration-300 hover:scale-[1.01] {dark
    ? 'border-slate-700 bg-slate-900/90 text-slate-50 shadow-xl shadow-black/40'
    : 'border-slate-800/80 bg-slate-900/50 text-slate-100'} {cls}"
>
  <div class="flex items-start justify-between gap-3">
    <div class="space-y-1.5">
      <p class="text-caption font-bold uppercase tracking-widest text-slate-400">
        {title}
      </p>
      {#if value !== null}
        <h3
          class="text-3xl font-extrabold tracking-tight {dark ? 'text-slate-50' : 'text-slate-100'}"
        >
          {value}
        </h3>
      {/if}
    </div>

    {#if icon}
      {@const SvelteComponent = icon}
      <div
        class="flex h-10 w-10 items-center justify-center rounded-2xl {dark
          ? 'bg-white/10 text-white'
          : 'bg-slate-800 text-slate-400'} shrink-0"
      >
        <SvelteComponent class="h-5 w-5" />
      </div>
    {/if}
  </div>

  {#if children}
    <div class="mt-4">
      {@render children?.()}
    </div>
  {/if}

  {#if description || trend}
    <div class="mt-4 flex items-center gap-2 text-xs">
      {#if trend}
        <span
          class="rounded-md px-2 py-0.5 font-semibold {trendUp === true
            ? 'border border-emerald-800 bg-emerald-950/80 text-emerald-400'
            : trendUp === false
              ? 'border border-rose-800 bg-rose-950/80 text-rose-400'
              : 'bg-slate-800 text-slate-300'}"
        >
          {trend}
        </span>
      {/if}
      {#if description}
        <p class="truncate text-slate-400">
          {description}
        </p>
      {/if}
    </div>
  {/if}
</div>
