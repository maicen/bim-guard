<script lang="ts">
  import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from 'lucide-svelte';

  let {
    type = 'info',
    title = null,
    message = '',
    dismissible = false,
    onDismiss = null,
  }: {
    type?: 'error' | 'warning' | 'success' | 'info';
    title?: string | null;
    message?: string;
    dismissible?: boolean;
    onDismiss?: (() => void) | null;
  } = $props();

  let visible = $state(true);

  function handleDismiss() {
    visible = false;
    if (onDismiss) onDismiss();
  }

  const CONFIG = {
    error: {
      bg: 'bg-rose-950/40 border-rose-800/80 text-rose-200',
      icon: AlertCircle,
      iconColor: 'text-rose-400',
    },
    warning: {
      bg: 'bg-amber-950/40 border-amber-800/80 text-amber-200',
      icon: AlertTriangle,
      iconColor: 'text-amber-400',
    },
    success: {
      bg: 'bg-emerald-950/40 border-emerald-800/80 text-emerald-200',
      icon: CheckCircle2,
      iconColor: 'text-emerald-400',
    },
    info: {
      bg: 'bg-blue-950/40 border-blue-800/80 text-blue-200',
      icon: Info,
      iconColor: 'text-blue-400',
    },
  };

  let conf = $derived(CONFIG[type] || CONFIG.info);
  let Icon = $derived(conf.icon);
</script>

{#if visible && message}
  <div
    role="alert"
    class="p-4 rounded-2xl border flex items-start justify-between gap-3 text-xs leading-relaxed transition-all {conf.bg}"
  >
    <div class="flex items-start gap-3 min-w-0">
      <Icon class="w-4 h-4 shrink-0 mt-0.5 {conf.iconColor}" />
      <div class="space-y-0.5 min-w-0">
        {#if title}
          <div class="font-bold text-white text-[13px] tracking-tight">
            {title}
          </div>
        {/if}
        <div class="text-slate-300">
          {message}
        </div>
      </div>
    </div>

    {#if dismissible}
      <button
        type="button"
        onclick={handleDismiss}
        class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors shrink-0"
        title="Dismiss alert"
      >
        <X class="w-3.5 h-3.5" />
      </button>
    {/if}
  </div>
{/if}
