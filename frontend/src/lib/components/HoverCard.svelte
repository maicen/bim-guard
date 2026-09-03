<!--
  HoverCard — reusable rich-preview popover.

  Shows supplementary detail about the thing under the pointer without
  spending a click or a modal. Modelled on the shadcn/Base UI hover card
  (https://ui.shadcn.com/docs/components/base/hover-card) and re-implemented
  in Svelte + Tailwind against the BIM-Guard slate token palette.

  Usage:

      <HoverCard side="top" align="start" title="GC-001" icon={Zap}>
        <span slot="trigger" class="font-mono">GC-001</span>
        Galvanic corrosion between dissimilar metals.
      </HoverCard>

  The `trigger` slot is what the user points at; the default slot is the
  card body. A `footer` slot renders a divided strip at the bottom.

  Notes on behaviour:
  - The card is portalled to <body> and positioned with fixed coordinates.
    Every data table in this app sits inside `overflow-x-auto` / `overflow-hidden`
    containers, which would clip an absolutely positioned popup.
  - `side` is a preference, not a guarantee: the card flips to the opposite
    side and clamps into the viewport when there is not enough room.
  - Opens on hover AND on keyboard focus, closes on Escape — the content is
    reachable without a mouse. Content here must stay supplementary: anything
    essential belongs in the row or the details modal, per the hover card's
    documented accessibility contract.
-->
<script lang="ts">
  import { onDestroy, tick, untrack } from "svelte";
  import type { ComponentType } from "svelte";

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
    trigger?: import("svelte").Snippet;
    children?: import("svelte").Snippet;
    footer?: import("svelte").Snippet;
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
    trigger,
    children,
    footer,
  }: Props = $props();

  let triggerEl: HTMLElement | null = $state(null);
  let popupEl: HTMLElement | null = $state(null);
  let open = $state(false);
  let placed = $state(false);
  // `side` is only a preference: this holds the side actually used after the
  // flip/clamp pass in position(), which re-reads the prop each time it runs.
  let resolvedSide: Side = $state(untrack(() => side));
  let x = $state(0);
  let y = $state(0);
  let arrowX = $state(0);
  let arrowY = $state(0);

  let openTimer: ReturnType<typeof setTimeout> | null = null;
  let closeTimer: ReturnType<typeof setTimeout> | null = $state(null);
  let uid = `hovercard-${Math.random().toString(36).slice(2, 9)}`;

  const OPPOSITE: Record<Side, Side> = {
    top: "bottom",
    bottom: "top",
    left: "right",
    right: "left",
  };

  /** Move a node to <body> so table overflow containers cannot clip it. */
  function portal(node: HTMLElement) {
    document.body.appendChild(node);
    return {
      destroy() {
        node.remove();
      },
    };
  }

  function clearTimers() {
    if (openTimer) clearTimeout(openTimer);
    if (closeTimer) clearTimeout(closeTimer);
    openTimer = null;
    closeTimer = null;
  }

  async function show() {
    if (disabled || open) return;
    open = true;
    placed = false;
    await tick();
    place();
    placed = true;
  }

  function hide() {
    open = false;
    placed = false;
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

  /** Resolve the card's viewport position against the trigger rect. */
  function place() {
    if (!triggerEl || !popupEl) return;

    const t = triggerEl.getBoundingClientRect();
    const p = popupEl.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const edge = 8;

    const room: Record<Side, number> = {
      top: t.top,
      bottom: vh - t.bottom,
      left: t.left,
      right: vw - t.right,
    };
    const vertical = side === "top" || side === "bottom";
    const needed = (vertical ? p.height : p.width) + sideOffset;

    let s: Side = side;
    if (room[s] < needed && room[OPPOSITE[s]] > room[s]) s = OPPOSITE[s];
    resolvedSide = s;

    let left: number;
    let top: number;

    if (s === "top" || s === "bottom") {
      top = s === "top" ? t.top - p.height - sideOffset : t.bottom + sideOffset;
      left =
        align === "start"
          ? t.left
          : align === "end"
            ? t.right - p.width
            : t.left + t.width / 2 - p.width / 2;
    } else {
      left = s === "left" ? t.left - p.width - sideOffset : t.right + sideOffset;
      top =
        align === "start"
          ? t.top
          : align === "end"
            ? t.bottom - p.height
            : t.top + t.height / 2 - p.height / 2;
    }

    left = Math.min(Math.max(edge, left), Math.max(edge, vw - p.width - edge));
    top = Math.min(Math.max(edge, top), Math.max(edge, vh - p.height - edge));

    // Keep the arrow aimed at the trigger even after the card is clamped.
    arrowX = Math.min(Math.max(12, t.left + t.width / 2 - left), p.width - 12);
    arrowY = Math.min(Math.max(12, t.top + t.height / 2 - top), p.height - 12);

    x = Math.round(left);
    y = Math.round(top);
  }

  /** Tap/click support: hover does not exist on touch devices. */
  function toggle() {
    clearTimers();
    if (open) hide();
    else show();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && open) {
      clearTimers();
      hide();
    }
  }

  // A scrolling table or window resize invalidates the cached rect, so the
  // card is repositioned rather than left floating over unrelated rows.
  // Capture phase catches scroll on nested containers, which does not bubble.
  function handleReflow() {
    if (open) place();
  }

  let arrowStyle = $derived(
    resolvedSide === "top"
      ? `left:${arrowX}px;bottom:-4px;`
      : resolvedSide === "bottom"
        ? `left:${arrowX}px;top:-4px;`
        : resolvedSide === "left"
          ? `top:${arrowY}px;right:-4px;`
          : `top:${arrowY}px;left:-4px;`,
  );

  let arrowBorders = $derived(
    resolvedSide === "top"
      ? "border-r border-b"
      : resolvedSide === "bottom"
        ? "border-l border-t"
        : resolvedSide === "left"
          ? "border-t border-r"
          : "border-b border-l",
  );

  onDestroy(clearTimers);
</script>

<svelte:window onkeydown={handleKeydown} onresize={handleReflow} onscrollcapture={handleReflow} />

<!--
  A focusable trigger is a real <button>, not a span carrying tabindex: it is
  reachable by keyboard and, because hover does not exist on touch, tapping it
  opens the card too. Triggers that already wrap their own control (the engine
  checkboxes) pass focusable={false} and stay a plain span — focus bubbling
  from inside still opens the card.
-->
{#if focusable && !disabled}
  <button
    type="button"
    bind:this={triggerEl}
    class="inline-flex text-left {triggerClass}"
    aria-describedby={open ? uid : undefined}
    aria-expanded={open}
    onmouseenter={scheduleOpen}
    onmouseleave={scheduleClose}
    onfocusin={show}
    onfocusout={scheduleClose}
    onclick={toggle}
  >
    {@render trigger?.()}
  </button>
{:else}
  <span
    bind:this={triggerEl}
    class="inline-flex text-left {triggerClass}"
    aria-describedby={open ? uid : undefined}
    onmouseenter={scheduleOpen}
    onmouseleave={scheduleClose}
    onfocusin={show}
    onfocusout={scheduleClose}
    role="presentation"
  >
    {@render trigger?.()}
  </span>
{/if}

{#if open}
  <div
    use:portal
    bind:this={popupEl}
    id={uid}
    role="tooltip"
    style="position:fixed;left:{x}px;top:{y}px;"
    class="z-[60] {width} max-w-[calc(100vw-1rem)] transition-[opacity,transform] duration-150 ease-out {placed
      ? 'translate-y-0 scale-100 opacity-100'
      : 'translate-y-0.5 scale-[0.98] opacity-0'}"
    onmouseenter={() => {
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
    }}
    onmouseleave={scheduleClose}
  >
    <div
      class="relative rounded-xl border border-slate-800 bg-slate-900/95 shadow-2xl shadow-black/40 backdrop-blur-md {contentClass}"
    >
      {#if showArrow}
        <span
          aria-hidden="true"
          style={arrowStyle}
          class="absolute h-2 w-2 rotate-45 border-slate-800 bg-slate-900 {arrowBorders}"
        ></span>
      {/if}

      {#if title || icon || subtitle}
        <div class="flex items-start gap-2.5 border-b border-slate-800/80 px-3.5 pb-2 pt-3">
          {#if icon}
            {@const SvelteComponent = icon}
            <div
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-blue-800/50 bg-blue-950/50 text-accent"
            >
              <SvelteComponent class="h-3.5 w-3.5" />
            </div>
          {/if}
          <div class="min-w-0">
            {#if title}
              <div class="break-words text-xs font-bold tracking-tight text-slate-100">
                {title}
              </div>
            {/if}
            {#if subtitle}
              <div class="mt-0.5 break-words text-micro text-slate-400">
                {subtitle}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <div class="px-3.5 py-2.5 text-caption leading-relaxed text-slate-300">
        {@render children?.()}
      </div>

      {#if footer && showFooter}
        <div class="border-t border-slate-800/80 px-3.5 py-2 text-micro text-slate-400">
          {@render footer?.()}
        </div>
      {/if}
    </div>
  </div>
{/if}
