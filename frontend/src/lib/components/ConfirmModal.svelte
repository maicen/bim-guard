<script lang="ts">
  import { AlertDialog as AlertDialogPrimitive } from "bits-ui";
  import { AlertTriangle } from "lucide-svelte";
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

  let isSubmitting = $state(false);

  async function handleConfirm() {
    isSubmitting = true;
    try {
      await onConfirm();
      isOpen = false;
    } finally {
      isSubmitting = false;
    }
  }

  function handleCancel() {
    if (isSubmitting) return;
    onCancel();
    isOpen = false;
  }
</script>

<AlertDialogPrimitive.Root
  open={isOpen}
  onOpenChange={(v) => {
    if (!v) handleCancel();
  }}
>
  <AlertDialogPrimitive.Portal>
    <AlertDialogPrimitive.Overlay
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs transition-all duration-200 animate-in fade-in"
    />
    <AlertDialogPrimitive.Content
      class="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 space-y-5 rounded-2xl border border-border-default bg-surface-card p-6 shadow-2xl transition-all duration-200 animate-in fade-in zoom-in-95 focus:outline-hidden"
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
          <AlertDialogPrimitive.Title class="text-base font-bold tracking-tight text-fg-primary">
            {title}
          </AlertDialogPrimitive.Title>
          <AlertDialogPrimitive.Description class="text-xs leading-relaxed text-fg-muted">
            {message}
          </AlertDialogPrimitive.Description>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2.5 border-t border-border-subtle pt-3">
        <AlertDialogPrimitive.Cancel
          onclick={handleCancel}
          disabled={isSubmitting}
          class="h-9 rounded-xl border border-border-default bg-surface-overlay px-4 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
        >
          {cancelText}
        </AlertDialogPrimitive.Cancel>

        <AlertDialogPrimitive.Action
          onclick={handleConfirm}
          disabled={isSubmitting}
          class={cn(
            "inline-flex h-9 items-center justify-center gap-1.5 rounded-xl px-4 text-xs font-semibold text-white shadow-xs transition-colors focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50",
            danger ? "bg-critical hover:bg-critical/90" : "bg-accent hover:bg-accent-hover",
          )}
        >
          {#if isSubmitting}
            <span class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
          {/if}
          <span>{isSubmitting ? "Processing..." : confirmText}</span>
        </AlertDialogPrimitive.Action>
      </div>
    </AlertDialogPrimitive.Content>
  </AlertDialogPrimitive.Portal>
</AlertDialogPrimitive.Root>
