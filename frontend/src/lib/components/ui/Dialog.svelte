<script lang="ts" module>
  import { Dialog as DialogPrimitive } from "bits-ui";

  export const DialogRoot = DialogPrimitive.Root;
  export const DialogTrigger = DialogPrimitive.Trigger;
  export const DialogPortal = DialogPrimitive.Portal;
  export const DialogOverlay = DialogPrimitive.Overlay;
  export const DialogContent = DialogPrimitive.Content;
  export const DialogTitle = DialogPrimitive.Title;
  export const DialogDescription = DialogPrimitive.Description;
  export const DialogClose = DialogPrimitive.Close;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { X } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  interface Props {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    title?: string;
    description?: string;
    maxWidth?: "max-w-sm" | "max-w-md" | "max-w-lg" | "max-w-xl" | "max-w-2xl" | "max-w-3xl" | "max-w-4xl";
    class?: string;
    trigger?: Snippet<[Record<string, any>]>;
    headerExtra?: Snippet;
    children?: Snippet;
    footer?: Snippet;
  }

  let {
    open = $bindable(false),
    onOpenChange,
    title = "",
    description = "",
    maxWidth = "max-w-lg",
    class: className,
    trigger,
    headerExtra,
    children,
    footer,
  }: Props = $props();
</script>

<DialogPrimitive.Root bind:open {onOpenChange}>
  {#if trigger}
    <DialogPrimitive.Trigger>
      {#snippet child({ props })}
        {@render trigger({ ...props })}
      {/snippet}
    </DialogPrimitive.Trigger>
  {/if}

  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay
      class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md transition-all duration-200 animate-in fade-in"
    />
    <DialogPrimitive.Content
      class={cn(
        "fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-2xl transition-all duration-200 animate-in fade-in zoom-in-95 focus:outline-hidden",
        maxWidth,
        className,
      )}
    >
      {#if title || headerExtra}
        <div class="flex shrink-0 items-center justify-between border-b border-border-default px-6 py-4">
          <div class="space-y-0.5">
            {#if title}
              <DialogPrimitive.Title class="text-sm font-bold text-fg-primary">
                {title}
              </DialogPrimitive.Title>
            {/if}
            {#if description}
              <DialogPrimitive.Description class="text-xs text-fg-muted">
                {description}
              </DialogPrimitive.Description>
            {/if}
          </div>
          <div class="flex items-center gap-2">
            {@render headerExtra?.()}
            <DialogPrimitive.Close
              class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary focus-visible:outline-2 focus-visible:outline-accent"
              aria-label="Close dialog"
            >
              <X class="h-4 w-4" />
            </DialogPrimitive.Close>
          </div>
        </div>
      {/if}

      <div class="flex-1 overflow-y-auto p-6 text-xs text-fg-secondary">
        {@render children?.()}
      </div>

      {#if footer}
        <div class="flex shrink-0 items-center justify-end gap-2.5 border-t border-border-default bg-surface-canvas/40 px-6 py-3.5">
          {@render footer()}
        </div>
      {/if}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
</DialogPrimitive.Root>
