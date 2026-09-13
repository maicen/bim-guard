<script lang="ts">
  import type { Component, ComponentType, Snippet } from "svelte";
  import { Dialog as DialogPrimitive } from "bits-ui";
  import { X } from "lucide-svelte";
  import { cn } from "../utils/cn";

  let {
    isOpen = false,
    title = "",
    subtitle = "",
    icon = null,
    maxWidth = "max-w-lg",
    closeOnBackdrop = true,
    onClose,
    children,
    headerExtra,
    footer,
  }: {
    isOpen?: boolean;
    title?: string;
    subtitle?: string;
    icon?: Component<any> | ComponentType<any> | null;
    maxWidth?:
      "max-w-sm" | "max-w-md" | "max-w-lg" | "max-w-xl" | "max-w-2xl" | "max-w-3xl" | "max-w-4xl";
    /** Dismiss when the backdrop itself is clicked. */
    closeOnBackdrop?: boolean;
    onClose: () => void;
    children?: Snippet;
    headerExtra?: Snippet;
    footer?: Snippet;
  } = $props();

  const Icon = $derived(icon);

  function handleOpenChange(open: boolean) {
    if (!open) onClose();
  }
</script>

<DialogPrimitive.Root open={isOpen} onOpenChange={handleOpenChange}>
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay
      class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md transition-all duration-200 animate-in fade-in"
    />
    <DialogPrimitive.Content
      interactOutsideBehavior={closeOnBackdrop ? "close" : "ignore"}
      class={cn(
        "fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-2xl transition-all duration-200 animate-in fade-in zoom-in-95 focus:outline-hidden",
        maxWidth,
      )}
    >
      <div
        class="flex items-center justify-between gap-4 border-b border-border-subtle bg-surface-canvas/60 px-6 py-4"
      >
        <div class="flex min-w-0 items-center gap-3">
          {#if Icon}
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent"
            >
              <Icon class="h-4 w-4" />
            </div>
          {/if}
          <div class="min-w-0">
            <DialogPrimitive.Title class="truncate text-base font-bold tracking-tight text-fg-primary">
              {title}
            </DialogPrimitive.Title>
            {#if subtitle}
              <DialogPrimitive.Description class="mt-0.5 truncate text-xs text-fg-muted">
                {subtitle}
              </DialogPrimitive.Description>
            {/if}
          </div>
        </div>

        <div class="flex shrink-0 items-center gap-2">
          {@render headerExtra?.()}
          <DialogPrimitive.Close
            onclick={onClose}
            class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary focus-visible:outline-2 focus-visible:outline-accent"
            aria-label="Close dialog"
          >
            <X class="h-4 w-4" />
          </DialogPrimitive.Close>
        </div>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto p-6 text-xs text-fg-secondary">
        {@render children?.()}
      </div>

      {#if footer}
        <div
          class="flex shrink-0 items-center justify-end gap-2 border-t border-border-default bg-surface-canvas/80 px-6 py-3.5"
        >
          {@render footer()}
        </div>
      {/if}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
</DialogPrimitive.Root>
