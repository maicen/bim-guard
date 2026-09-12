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
      bg: "bg-critical-bg border-critical-border text-critical",
      icon: AlertCircle,
      iconColor: "text-critical",
    },
    warning: {
      bg: "bg-warning-bg border-warning-border text-warning",
      icon: AlertTriangle,
      iconColor: "text-warning",
    },
    success: {
      bg: "bg-success-bg border-success-border text-success",
      icon: CheckCircle2,
      iconColor: "text-success",
    },
    info: {
      bg: "bg-info-bg border-info-border text-info",
      icon: Info,
      iconColor: "text-info",
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
          <div class="text-[13px] font-bold tracking-tight text-fg-primary">
            {title}
          </div>
        {/if}
        <div class="text-fg-secondary">
          {message}
        </div>
      </div>
    </div>

    {#if dismissible}
      <button
        type="button"
        onclick={handleDismiss}
        class="shrink-0 rounded-lg p-1 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
        title="Dismiss alert"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    {/if}
  </div>
{/if}
