<script lang="ts">
  import type { Component, ComponentType, Snippet } from "svelte";
  import { X } from "lucide-svelte";
  import { dialog, dialogId } from "../utils/dialog.svelte";
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
      | "max-w-sm"
      | "max-w-md"
      | "max-w-lg"
      | "max-w-xl"
      | "max-w-2xl"
      | "max-w-3xl"
      | "max-w-4xl";
    /** Dismiss when the backdrop itself is clicked. */
    closeOnBackdrop?: boolean;
    onClose: () => void;
    children?: Snippet;
    headerExtra?: Snippet;
    footer?: Snippet;
  } = $props();

  // Per-instance so two dialogs of the same type never collide on one DOM id.
  const titleId = dialogId("modal-title");
  const Icon = $derived(icon);

  function handleBackdropClick(event: MouseEvent) {
    // Only a click that both starts and ends on the backdrop dismisses, so a
    // drag that began inside the card does not close it.
    if (closeOnBackdrop && event.target === event.currentTarget) onClose();
  }
</script>

{#if isOpen}
  <!-- The backdrop is a click target, not a control: keyboard users dismiss with
       Escape, which the `dialog` attachment handles. -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="animate-in fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md duration-200"
    role="dialog"
    aria-modal="true"
    aria-labelledby={titleId}
    tabindex="-1"
    onclick={handleBackdropClick}
    {@attach dialog(onClose)}
  >
    <div
      class={cn(
        "animate-in zoom-in-95 flex max-h-[90vh] w-full flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl duration-200",
        maxWidth,
      )}
    >
      <div
        class="flex items-center justify-between gap-4 border-b border-slate-800 bg-slate-950/60 px-6 py-4"
      >
        <div class="flex min-w-0 items-center gap-3">
          {#if Icon}
            <div
              class="text-accent flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-blue-800/60 bg-blue-950/60"
            >
              <Icon class="h-4 w-4" />
            </div>
          {/if}
          <div class="min-w-0">
            <h3 id={titleId} class="truncate text-base font-bold tracking-tight text-slate-50">
              {title}
            </h3>
            {#if subtitle}
              <p class="mt-0.5 truncate text-xs text-slate-400">{subtitle}</p>
            {/if}
          </div>
        </div>

        <div class="flex shrink-0 items-center gap-2">
          {@render headerExtra?.()}
          <button
            type="button"
            onclick={onClose}
            class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
            aria-label="Close dialog"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto p-6 text-xs">
        {@render children?.()}
      </div>

      {#if footer}
        <div
          class="flex shrink-0 items-center justify-end gap-2 border-t border-slate-800 bg-slate-950/80 px-6 py-3.5"
        >
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}
