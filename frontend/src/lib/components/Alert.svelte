<script lang="ts">
  import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-svelte";
  import { buildIssueLog, copyToClipboard, type ErrorLogEntry } from "../utils/errorLog";

  let {
    type = "info",
    title = null,
    message = "",
    dismissible = false,
    onDismiss = null,
    errors = null,
    logTitle = "Error Log",
    logContext = {},
    children,
  }: {
    type?: "error" | "warning" | "success" | "info";
    title?: string | null;
    message?: string;
    dismissible?: boolean;
    onDismiss?: (() => void) | null;
    errors?: ErrorLogEntry[] | null;
    logTitle?: string;
    logContext?: Record<string, string | number | undefined>;
    children?: import('svelte').Snippet;
  } = $props();

  let visible = $state(true);
  let showDetails = $state(false);
  let copied = $state(false);

  function handleDismiss() {
    visible = false;
    showDetails = false;
    if (onDismiss) onDismiss();
  }

  async function handleCopy() {
    const ok = await copyToClipboard(buildIssueLog(logTitle, logContext, errors || []));
    if (ok) {
      copied = true;
      setTimeout(() => (copied = false), 2000);
    }
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

{#if visible && (message || children)}
  <div class="space-y-2">
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
          {#if message}
            <div class="text-fg-secondary">
              {message}
            </div>
          {/if}
          {#if children}
            <div class="text-fg-secondary">
              {@render children()}
            </div>
          {/if}
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

    {#if errors && errors.length > 0}
      <div class="rounded-2xl border border-border-default/90 bg-surface-canvas/80 p-3">
        <div class="flex items-center justify-between gap-2">
          <button
            type="button"
            class="text-xs font-semibold text-fg-secondary hover:text-fg-primary"
            onclick={() => (showDetails = !showDetails)}
          >
            {showDetails ? "Hide" : "Show"} technical details ({errors.length} issue{errors.length ===
            1
              ? ""
              : "s"})
          </button>
          <button
            type="button"
            class="rounded-lg border border-border-default px-2.5 py-1 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
            onclick={handleCopy}
          >
            {copied ? "Copied!" : "Copy issue log"}
          </button>
        </div>
        {#if showDetails}
          <pre
            class="mt-2 max-h-64 overflow-auto rounded-xl border border-border-subtle bg-surface-card p-3 text-[11px] leading-relaxed text-fg-muted">{buildIssueLog(
              logTitle,
              logContext,
              errors,
            )}</pre>
        {/if}
      </div>
    {/if}
  </div>
{/if}
