<script lang="ts">
  import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-svelte";

  let {
    type = "info",
    title = null,
    message = "",
    dismissible = false,
    onDismiss = null,
  }: {
    type?: "error" | "warning" | "success" | "info";
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
      bg: "bg-rose-950/40 border-rose-800/80 text-rose-200",
      icon: AlertCircle,
      iconColor: "text-rose-400",
    },
    warning: {
      bg: "bg-amber-950/40 border-amber-800/80 text-amber-200",
      icon: AlertTriangle,
      iconColor: "text-amber-400",
    },
    success: {
      bg: "bg-emerald-950/40 border-emerald-800/80 text-emerald-200",
      icon: CheckCircle2,
      iconColor: "text-emerald-400",
    },
    info: {
      bg: "bg-blue-950/40 border-blue-800/80 text-blue-200",
      icon: Info,
      iconColor: "text-blue-400",
    },
  };

  let conf = $derived(CONFIG[type] || CONFIG.info);
  let Icon = $derived(conf.icon);
</script>

{#if visible && message}
  <div
    role="alert"
    class="flex items-start justify-between gap-3 rounded-2xl border p-4 text-xs leading-relaxed transition-all {conf.bg}"
  >
    <div class="flex min-w-0 items-start gap-3">
      <Icon class="mt-0.5 h-4 w-4 shrink-0 {conf.iconColor}" />
      <div class="min-w-0 space-y-0.5">
        {#if title}
          <div class="text-[13px] font-bold tracking-tight text-slate-50">
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
        class="shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-500/10 hover:text-slate-50"
        title="Dismiss alert"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    {/if}
  </div>
{/if}
