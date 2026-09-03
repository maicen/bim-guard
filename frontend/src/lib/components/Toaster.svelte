<script lang="ts">
  import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-svelte";
  import { toasts, type ToastVariant } from "../toast.svelte";
  import { cn } from "../utils/cn";

  const ICONS = {
    success: CheckCircle2,
    error: XCircle,
    warning: AlertTriangle,
    info: Info,
  } as const;

  const STYLES: Record<ToastVariant, string> = {
    success: "border-emerald-800/80 bg-emerald-950/90 text-emerald-200",
    error: "border-rose-800/80 bg-rose-950/90 text-rose-200",
    warning: "border-amber-800/80 bg-amber-950/90 text-amber-200",
    info: "border-blue-800/80 bg-blue-950/90 text-blue-200",
  };
</script>

<!--
  A single live region for the whole app. Errors are assertive so they interrupt;
  everything else is polite. The container is always present so screen readers
  register it before the first message arrives.
-->
<div
  class="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
  role="region"
  aria-label="Notifications"
>
  {#each toasts.items as toast (toast.id)}
    {@const Icon = ICONS[toast.variant]}
    <div
      role={toast.variant === "error" ? "alert" : "status"}
      aria-live={toast.variant === "error" ? "assertive" : "polite"}
      class={cn(
        "pointer-events-auto flex items-start gap-3 rounded-xl border p-3 shadow-2xl backdrop-blur-md duration-200 animate-in fade-in slide-in-from-bottom-2",
        STYLES[toast.variant],
      )}
    >
      <Icon class="mt-0.5 h-4 w-4 shrink-0" />
      <div class="min-w-0 flex-1">
        {#if toast.title}
          <p class="text-xs font-bold tracking-tight">{toast.title}</p>
        {/if}
        <p class="break-words text-xs leading-relaxed">{toast.message}</p>
      </div>
      <button
        type="button"
        onclick={() => toasts.dismiss(toast.id)}
        class="shrink-0 rounded-lg p-1 opacity-70 transition-opacity hover:opacity-100"
        aria-label="Dismiss notification"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </div>
  {/each}
</div>
