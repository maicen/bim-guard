<!--
  HoverCard — reusable rich-preview popover.

  Shows supplementary detail about the thing under the pointer without
  spending a click or a modal. Built on bits-ui's `Popover` primitive
  (Floating UI positioning/collision handling, Escape and outside-click
  dismissal) styled to match the BIM-Guard slate token palette.

  Usage:

      <HoverCard side="top" align="start" title="GC-001" icon={Zap}>
        {#snippet trigger()}<span class="font-mono">GC-001</span>{/snippet}
        Galvanic corrosion between dissimilar metals.
      </HoverCard>

  The `trigger` snippet is what the user points at; the default snippet is
  the card body. A `footer` snippet renders a divided strip at the bottom.

  Notes on behaviour:
  - Opens on hover AND on keyboard focus, closes on Escape, an outside click,
    or on focus/pointer leaving — reachable without a mouse. Content here
    must stay supplementary: anything essential belongs in the row or the
    details modal, per the hover card's documented accessibility contract.
  - `side` is a preference, not a guarantee: bits-ui flips to the opposite
    side and clamps into the viewport when there is not enough room, and
    keeps the card positioned as the trigger scrolls or the window resizes.
-->
<script lang="ts">
  import { onDestroy } from "svelte";
  import type { Snippet } from "svelte";
  import type { ComponentType } from "svelte";
  import { Popover } from "bits-ui";
  import { cn } from "../utils/cn";

  type Side = "top" | "bottom" | "left" | "right";
  type Align = "start" | "center" | "end";

  interface Props {
    /** Preferred side of the trigger to render on. Flips when space is tight. */
    side?: Side;
    /** Alignment along the trigger's cross axis. */
    align?: Align;
    /** Gap in px between trigger and card. */
    sideOffset?: number;
    /** Delay before opening on hover (ms). */
    openDelay?: number;
    /** Grace period before closing (ms) — lets the pointer cross the gap. */
    closeDelay?: number;
    /** Tailwind width class for the card. */
    width?: string;
    /** Optional card heading. */
    title?: string;
    /** Optional secondary line under the heading. */
    subtitle?: string;
    /** Optional lucide icon rendered in the heading. */
    icon?: ComponentType | null;
    /** Suppress the card entirely (e.g. nothing worth previewing). */
    disabled?: boolean;
    /** Fired the moment the card starts opening — for callers that lazily
     *  fetch the preview content instead of holding it upfront. */
    onOpen?: () => void;
    /** Render the trigger as a real <button>, so it is keyboard reachable and
     *  tappable. Turn off when the trigger already wraps its own interactive
     *  control (a label, a link) — focus inside it still opens the card. */
    focusable?: boolean;
    /** Draw the pointer arrow. */
    showArrow?: boolean;
    /** Render the footer strip. A `slot="footer"` element must be a direct child
     *  of this component, so it cannot be wrapped in `{#if}` at the call site —
     *  callers gate an optional footer with this instead of an empty strip. */
    showFooter?: boolean;
    /** Extra classes on the inline trigger wrapper. */
    triggerClass?: string;
    /** Extra classes on the card body. */
    contentClass?: string;
    trigger?: Snippet;
    children?: Snippet;
    footer?: Snippet;
  }

  let {
    side = "top",
    align = "center",
    sideOffset = 8,
    openDelay = 180,
    closeDelay = 120,
    width = "w-72",
    title = "",
    subtitle = "",
    icon = null,
    disabled = false,
    focusable = true,
    showArrow = true,
    showFooter = true,
    triggerClass = "",
    contentClass = "",
    onOpen,
    trigger,
    children,
    footer,
  }: Props = $props();

  let open = $state(false);

  // bits-ui's own `openOnHover` uses an internal grace-area heuristic that
  // proved unreliable here (it can leave the card open indefinitely once the
  // pointer has left both the trigger and the card). Driving `open` with our
  // own explicit open/close timers — the same scheme the original hand-rolled
  // implementation used — keeps that behaviour predictable while still
  // handing positioning, portalling, and Escape/outside-click dismissal to
  // bits-ui's `Popover`.
  let openTimer: ReturnType<typeof setTimeout> | null = null;
  let closeTimer: ReturnType<typeof setTimeout> | null = null;

  function clearTimers() {
    if (openTimer) clearTimeout(openTimer);
    if (closeTimer) clearTimeout(closeTimer);
    openTimer = null;
    closeTimer = null;
  }

  function show() {
    if (disabled || open) return;
    open = true;
    onOpen?.();
  }

  function hide() {
    open = false;
  }

  function scheduleOpen() {
    if (disabled) return;
    if (closeTimer) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
    if (open || openTimer) return;
    openTimer = setTimeout(() => {
      openTimer = null;
      show();
    }, openDelay);
  }

  function scheduleClose() {
    if (openTimer) {
      clearTimeout(openTimer);
      openTimer = null;
    }
    if (!open || closeTimer) return;
    closeTimer = setTimeout(() => {
      closeTimer = null;
      hide();
    }, closeDelay);
  }

  function cancelClose() {
    if (closeTimer) {
      clearTimeout(closeTimer);
      closeTimer = null;
    }
  }

  /** Reflects dismissal that bits-ui itself drives (Escape, outside click). */
  function handleOpenChange(next: boolean) {
    if (!next) clearTimers();
    open = next;
  }

  onDestroy(clearTimers);
</script>

{#if disabled}
  <span class={cn("inline-flex text-left", triggerClass)} role="presentation">
    {@render trigger?.()}
  </span>
{:else}
  <Popover.Root bind:open onOpenChange={handleOpenChange}>
    <Popover.Trigger
      onmouseenter={scheduleOpen}
      onmouseleave={scheduleClose}
      onfocusin={() => {
        clearTimers();
        show();
      }}
      onfocusout={scheduleClose}
    >
      {#snippet child({ props })}
        {#if focusable}
          <button type="button" {...props} class={cn("inline-flex text-left", triggerClass)}>
            {@render trigger?.()}
          </button>
        {:else}
          <span {...props} class={cn("inline-flex text-left", triggerClass)} role="presentation">
            {@render trigger?.()}
          </span>
        {/if}
      {/snippet}
    </Popover.Trigger>

    <Popover.Portal>
      <Popover.Content
        {side}
        {align}
        {sideOffset}
        onmouseenter={cancelClose}
        onmouseleave={scheduleClose}
        class={cn(
          "z-60 max-w-[calc(100vw-1rem)] rounded-xl border border-border-default bg-surface-card/95 shadow-2xl shadow-black/40 backdrop-blur-md outline-hidden origin-(--bits-popover-content-transform-origin) duration-150 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          width,
          contentClass,
        )}
      >
        {#if showArrow}
          <Popover.Arrow
            width={8}
            height={8}
            class="rotate-45 border-border-default bg-surface-card data-[side=top]:border-b data-[side=top]:border-r data-[side=bottom]:border-l data-[side=bottom]:border-t data-[side=left]:border-r data-[side=left]:border-t data-[side=right]:border-b data-[side=right]:border-l"
          />
        {/if}

        {#if title || icon || subtitle}
          <div class="flex items-start gap-2.5 border-b border-border-subtle px-3.5 pb-2 pt-3">
            {#if icon}
              {@const SvelteComponent = icon}
              <div
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-accent/30 bg-accent/10 text-accent"
              >
                <SvelteComponent class="h-3.5 w-3.5" />
              </div>
            {/if}
            <div class="min-w-0">
              {#if title}
                <div class="wrap-break-word text-xs font-bold tracking-tight text-fg-primary">
                  {title}
                </div>
              {/if}
              {#if subtitle}
                <div class="mt-0.5 wrap-break-word text-micro text-fg-muted">
                  {subtitle}
                </div>
              {/if}
            </div>
          </div>
        {/if}

        <div class="px-3.5 py-2.5 text-caption leading-relaxed text-fg-secondary">
          {@render children?.()}
        </div>

        {#if footer && showFooter}
          <div class="border-t border-border-subtle px-3.5 py-2 text-micro text-fg-muted">
            {@render footer?.()}
          </div>
        {/if}
      </Popover.Content>
    </Popover.Portal>
  </Popover.Root>
{/if}
