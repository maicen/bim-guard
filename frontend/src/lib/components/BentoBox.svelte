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
    ? 'border-border-default bg-surface-card text-fg-primary shadow-xl'
    : 'border-border-subtle bg-surface-card/80 text-fg-primary'} {cls}"
>
  <div class="flex items-start justify-between gap-3">
    <div class="space-y-1.5">
      <p class="text-caption font-bold uppercase tracking-widest text-fg-muted">
        {title}
      </p>
      {#if value !== null}
        <h3
          class="text-3xl font-extrabold tracking-tight text-fg-primary"
        >
          {value}
        </h3>
      {/if}
    </div>

    {#if icon}
      {@const SvelteComponent = icon}
      <div
        class="flex h-10 w-10 items-center justify-center rounded-2xl {dark
          ? 'bg-accent/15 text-accent'
          : 'bg-surface-overlay text-fg-secondary'} shrink-0"
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
            ? 'border border-success-border bg-success-bg text-success'
            : trendUp === false
              ? 'border border-critical-border bg-critical-bg text-critical'
              : 'border border-border-default bg-surface-overlay text-fg-secondary'}"
        >
          {trend}
        </span>
      {/if}
      {#if description}
        <p class="truncate text-fg-muted">
          {description}
        </p>
      {/if}
    </div>
  {/if}
</div>
