<script lang="ts" module>
  import { AlertDialog as AlertDialogPrimitive } from "bits-ui";

  export const AlertDialogRoot = AlertDialogPrimitive.Root;
  export const AlertDialogTrigger = AlertDialogPrimitive.Trigger;
  export const AlertDialogPortal = AlertDialogPrimitive.Portal;
  export const AlertDialogOverlay = AlertDialogPrimitive.Overlay;
  export const AlertDialogContent = AlertDialogPrimitive.Content;
  export const AlertDialogTitle = AlertDialogPrimitive.Title;
  export const AlertDialogDescription = AlertDialogPrimitive.Description;
  export const AlertDialogCancel = AlertDialogPrimitive.Cancel;
  export const AlertDialogAction = AlertDialogPrimitive.Action;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { AlertTriangle } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    title?: string;
    description?: string;
    confirmText?: string;
    cancelText?: string;
    danger?: boolean;
    loading?: boolean;
    onConfirm?: () => void | Promise<void>;
    onCancel?: () => void;
    children?: Snippet;
    trigger?: Snippet<[Record<string, any>]>;
  }

  let {
    open = $bindable(false),
    onOpenChange,
    title = "Confirm Action",
    description = "Are you sure you want to proceed? This action cannot be undone.",
    confirmText = "Confirm",
    cancelText = "Cancel",
    danger = true,
    loading = false,
    onConfirm,
    onCancel,
    children,
    trigger,
  }: Props = $props();

  let isSubmitting = $state(false);

  async function handleConfirm() {
    isSubmitting = true;
    try {
      await onConfirm?.();
      open = false;
    } finally {
      isSubmitting = false;
    }
  }

  function handleCancel() {
    if (isSubmitting) return;
    onCancel?.();
    open = false;
  }
</script>

<AlertDialogPrimitive.Root bind:open {onOpenChange}>
  {#if trigger}
    <AlertDialogPrimitive.Trigger>
      {#snippet child({ props })}
        {@render trigger({ ...props })}
      {/snippet}
    </AlertDialogPrimitive.Trigger>
  {/if}

  <AlertDialogPrimitive.Portal>
    <AlertDialogPrimitive.Overlay
      class="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs transition-all duration-200 animate-in fade-in"
    />
    <AlertDialogPrimitive.Content
      class="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-md -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-border-default bg-surface-card p-6 shadow-2xl transition-all duration-200 animate-in fade-in zoom-in-95 focus:outline-hidden"
    >
      <div class="flex items-start gap-4">
        <div
          class={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
            danger
              ? "border border-critical-border/50 bg-critical-bg text-critical"
              : "border border-warning-border/50 bg-warning-bg text-warning",
          )}
        >
          <AlertTriangle class="h-5 w-5" />
        </div>

        <div class="min-w-0 flex-1 space-y-1.5 pt-0.5">
          <AlertDialogPrimitive.Title class="text-sm font-bold text-fg-primary">
            {title}
          </AlertDialogPrimitive.Title>
          <AlertDialogPrimitive.Description class="text-xs leading-relaxed text-fg-secondary">
            {description}
          </AlertDialogPrimitive.Description>
          {#if children}
            <div class="pt-2">
              {@render children()}
            </div>
          {/if}
        </div>
      </div>

      <div class="mt-6 flex items-center justify-end gap-2.5">
        <AlertDialogPrimitive.Cancel
          onclick={handleCancel}
          disabled={isSubmitting || loading}
          class="h-8.5 rounded-xl border border-border-default bg-surface-canvas px-4 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
        >
          {cancelText}
        </AlertDialogPrimitive.Cancel>

        <AlertDialogPrimitive.Action
          onclick={handleConfirm}
          disabled={isSubmitting || loading}
          class={cn(
            "inline-flex h-8.5 items-center justify-center gap-1.5 rounded-xl px-4 text-xs font-semibold text-white shadow-xs transition-colors focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50",
            danger ? "bg-critical hover:bg-critical/90" : "bg-accent hover:bg-accent-hover",
          )}
        >
          {#if isSubmitting || loading}
            <span class="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
          {/if}
          <span>{confirmText}</span>
        </AlertDialogPrimitive.Action>
      </div>
    </AlertDialogPrimitive.Content>
  </AlertDialogPrimitive.Portal>
</AlertDialogPrimitive.Root>
