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
    class="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-black/60 px-4 backdrop-blur-sm"
    onclick={(e) => e.target === e.currentTarget && handleCancel()}
    {@attach dialog(handleCancel)}
  >
    <div
      class="w-full max-w-md animate-scale-up space-y-5 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-start gap-3.5">
        {#if danger}
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-rose-800/80 bg-rose-950/80 text-rose-400"
          >
            <AlertTriangle class="h-5 w-5" />
          </div>
        {/if}
        <div class="min-w-0 flex-1 space-y-1.5">
          <h2 id={titleId} class="text-base font-bold tracking-tight text-slate-50">
            {title}
          </h2>
          <p id={bodyId} class="text-xs leading-relaxed text-slate-400">
            {message}
          </p>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2.5 border-t border-slate-800/80 pt-2">
        <button
          type="button"
          onclick={handleCancel}
          disabled={isSubmitting}
          class="h-9 rounded-xl border border-slate-700 bg-slate-800 px-4 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50 disabled:opacity-50"
        >
          {cancelText}
        </button>

        <button
          type="button"
          onclick={handleConfirm}
          disabled={isSubmitting}
          class={cn(
            "h-9 rounded-xl px-4 text-xs font-semibold transition-all disabled:opacity-50",
            danger
              ? "bg-rose-600 text-white shadow-lg shadow-rose-950/50 hover:bg-rose-500"
              : "bg-accent text-white shadow-lg shadow-blue-950/50 hover:bg-accent-hover",
          )}
        >
          {isSubmitting ? "Processing..." : confirmText}
        </button>
      </div>
    </div>
  </div>
{/if}
