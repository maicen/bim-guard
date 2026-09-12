<script lang="ts">
  import { AlertTriangle } from "lucide-svelte";
  import { dialog, dialogId } from "../utils/dialog.svelte";
  import { cn } from "../utils/cn";

  let {
    isOpen = $bindable(false),
    title = "Confirm Action",
    message = "Are you sure you want to proceed? This action cannot be undone.",
    confirmText = "Delete",
    cancelText = "Cancel",
    danger = true,
    onConfirm,
    onCancel,
  }: {
    isOpen?: boolean;
    title?: string;
    message?: string;
    confirmText?: string;
    cancelText?: string;
    danger?: boolean;
    onConfirm: () => void | Promise<void>;
    onCancel: () => void;
  } = $props();

  const titleId = dialogId("confirm-title");
  const bodyId = dialogId("confirm-body");

  let isSubmitting = $state(false);

  async function handleConfirm() {
    isSubmitting = true;
    try {
      await onConfirm();
    } finally {
      isSubmitting = false;
      isOpen = false;
    }
  }

  function handleCancel() {
    // A confirmation must not vanish out from under an in-flight action.
    if (isSubmitting) return;
    onCancel();
    isOpen = false;
  }
</script>

{#if isOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    role="alertdialog"
    aria-modal="true"
    aria-labelledby={titleId}
    aria-describedby={bodyId}
    tabindex="-1"
    class="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-black/60 px-4 backdrop-blur-xs"
    onclick={(e) => e.target === e.currentTarget && handleCancel()}
    {@attach dialog(handleCancel)}
  >
    <div
      class="w-full max-w-md animate-scale-up space-y-5 rounded-2xl border border-border-default bg-surface-card p-6 shadow-2xl"
    >
      <div class="flex items-start gap-3.5">
        {#if danger}
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-critical-border bg-critical-bg text-critical"
          >
            <AlertTriangle class="h-5 w-5" />
          </div>
        {/if}
        <div class="min-w-0 flex-1 space-y-1.5">
          <h2 id={titleId} class="text-base font-bold tracking-tight text-fg-primary">
            {title}
          </h2>
          <p id={bodyId} class="text-xs leading-relaxed text-fg-muted">
            {message}
          </p>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2.5 border-t border-border-subtle pt-2">
        <button
          type="button"
          onclick={handleCancel}
          disabled={isSubmitting}
          class="h-9 rounded-xl border border-border-default bg-surface-overlay px-4 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary disabled:opacity-50"
        >
          {cancelText}
        </button>

        <button
          type="button"
          onclick={handleConfirm}
          disabled={isSubmitting}
          class={cn(
            "h-9 rounded-xl px-4 text-xs font-semibold text-white transition-all disabled:opacity-50",
            danger
              ? "bg-rose-600 hover:bg-rose-700 shadow-xs"
              : "bg-accent hover:bg-accent-hover shadow-xs",
          )}
        >
          {isSubmitting ? "Processing..." : confirmText}
        </button>
      </div>
    </div>
  </div>
{/if}
