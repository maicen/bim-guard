<script lang="ts">
  import type { Snippet } from 'svelte';

  type Variant =
    | 'critical'
    | 'high'
    | 'medium'
    | 'low'
    | 'data_quality'
    | 'complete'
    | 'running'
    | 'pending'
    | 'failed'
    | 'neutral';

  let {
    variant = 'neutral',
    size = 'sm',
    children,
  }: {
    variant?: Variant;
    size?: 'sm' | 'md';
    children?: Snippet;
  } = $props();

  const STYLES: Record<string, string> = {
    critical: 'bg-rose-950/80 border-rose-800 text-rose-300',
    high: 'bg-orange-950/80 border-orange-800 text-orange-300',
    medium: 'bg-amber-950/80 border-amber-800 text-amber-300',
    low: 'bg-emerald-950/80 border-emerald-800 text-emerald-300',
    data_quality: 'bg-slate-800/90 border-slate-700 text-slate-300',
    complete: 'bg-emerald-950/80 border-emerald-800 text-emerald-400',
    running: 'bg-blue-950/80 border-blue-800 text-blue-300 animate-pulse',
    pending: 'bg-slate-900 border-slate-800 text-slate-400',
    failed: 'bg-rose-950/80 border-rose-800 text-rose-400',
    neutral: 'bg-slate-800/80 border-slate-700 text-slate-300',
  };

  let normalizedKey = $derived((variant || '').toLowerCase().replace('-', '_'));
  let cls = $derived(STYLES[normalizedKey] || STYLES.neutral);
</script>

<span
  class="inline-flex items-center gap-1 font-semibold rounded-full border tracking-wide uppercase {size === 'sm'
    ? 'text-[10px] px-2 py-0.5'
    : 'text-xs px-2.5 py-1'} {cls}"
>
  {@render children?.()}
</span>
