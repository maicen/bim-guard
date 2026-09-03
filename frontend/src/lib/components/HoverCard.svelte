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
  import { onDestroy, tick } from "svelte";
  import type { ComponentType } from "svelte";

  type Side = "top" | "bottom" | "left" | "right";
  type Align = "start" | "center" | "end";

  /** Preferred side of the trigger to render on. Flips when space is tight. */
  export let side: Side = "top";
  /** Alignment along the trigger's cross axis. */
  export let align: Align = "center";
  /** Gap in px between trigger and card. */
  export let sideOffset: number = 8;
  /** Delay before opening on hover (ms). */
  export let openDelay: number = 180;
  /** Grace period before closing (ms) — lets the pointer cross the gap. */
  export let closeDelay: number = 120;
  /** Tailwind width class for the card. */
  export let width: string = "w-72";
  /** Optional card heading. */
  export let title: string = "";
  /** Optional secondary line under the heading. */
  export let subtitle: string = "";
  /** Optional lucide icon rendered in the heading. */
  export let icon: ComponentType | null = null;
  /** Suppress the card entirely (e.g. nothing worth previewing). */
  export let disabled: boolean = false;
  /** Render the trigger as a real <button>, so it is keyboard reachable and
   *  tappable. Turn off when the trigger already wraps its own interactive
   *  control (a label, a link) — focus inside it still opens the card. */
  export let focusable: boolean = true;
  /** Draw the pointer arrow. */
  export let showArrow: boolean = true;
  /** Render the footer strip. A `slot="footer"` element must be a direct child
   *  of this component, so it cannot be wrapped in `{#if}` at the call site —
   *  callers gate an optional footer with this instead of an empty strip. */
  export let showFooter: boolean = true;
  /** Extra classes on the inline trigger wrapper. */
  export let triggerClass: string = "";
  /** Extra classes on the card body. */
  export let contentClass: string = "";

  let triggerEl: HTMLElement | null = null;
  let popupEl: HTMLElement | null = null;
  let open = false;
  let placed = false;
  let resolvedSide: Side = side;
  let x = 0;
  let y = 0;
  let arrowX = 0;
  let arrowY = 0;

  let openTimer: ReturnType<typeof setTimeout> | null = null;
  let closeTimer: ReturnType<typeof setTimeout> | null = null;
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

  $: arrowStyle =
    resolvedSide === "top"
      ? `left:${arrowX}px;bottom:-4px;`
      : resolvedSide === "bottom"
        ? `left:${arrowX}px;top:-4px;`
        : resolvedSide === "left"
          ? `top:${arrowY}px;right:-4px;`
          : `top:${arrowY}px;left:-4px;`;

  $: arrowBorders =
    resolvedSide === "top"
      ? "border-r border-b"
      : resolvedSide === "bottom"
        ? "border-l border-t"
        : resolvedSide === "left"
          ? "border-t border-r"
          : "border-b border-l";

  onDestroy(clearTimers);
</script>

<svelte:window
  on:keydown={handleKeydown}
  on:resize={handleReflow}
  on:scroll|capture={handleReflow}
/>

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
    on:mouseenter={scheduleOpen}
    on:mouseleave={scheduleClose}
    on:focusin={show}
    on:focusout={scheduleClose}
    on:click={toggle}
  >
    <slot name="trigger" />
  </button>
{:else}
  <span
    bind:this={triggerEl}
    class="inline-flex text-left {triggerClass}"
    aria-describedby={open ? uid : undefined}
    on:mouseenter={scheduleOpen}
    on:mouseleave={scheduleClose}
    on:focusin={show}
    on:focusout={scheduleClose}
    role="presentation"
  >
    <slot name="trigger" />
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
      ? 'opacity-100 translate-y-0 scale-100'
      : 'opacity-0 translate-y-0.5 scale-[0.98]'}"
    on:mouseenter={() => {
      if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
      }
    }}
    on:mouseleave={scheduleClose}
  >
    <div
      class="relative rounded-xl border border-slate-800 bg-slate-900/95 backdrop-blur-md shadow-2xl shadow-black/40 {contentClass}"
    >
      {#if showArrow}
        <span
          aria-hidden="true"
          style={arrowStyle}
          class="absolute w-2 h-2 rotate-45 bg-slate-900 border-slate-800 {arrowBorders}"
        ></span>
      {/if}

      {#if title || icon || subtitle}
        <div
          class="flex items-start gap-2.5 px-3.5 pt-3 pb-2 border-b border-slate-800/80"
        >
          {#if icon}
            <div
              class="w-7 h-7 rounded-lg bg-blue-950/50 border border-blue-800/50 flex items-center justify-center text-accent shrink-0"
            >
              <svelte:component this={icon} class="w-3.5 h-3.5" />
            </div>
          {/if}
          <div class="min-w-0">
            {#if title}
              <div
                class="text-xs font-bold text-slate-100 tracking-tight break-words"
              >
                {title}
              </div>
            {/if}
            {#if subtitle}
              <div class="text-micro text-slate-400 mt-0.5 break-words">
                {subtitle}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <div class="px-3.5 py-2.5 text-caption leading-relaxed text-slate-300">
        <slot />
      </div>

      {#if $$slots.footer && showFooter}
        <div
          class="px-3.5 py-2 border-t border-slate-800/80 text-micro text-slate-400"
        >
          <slot name="footer" />
        </div>
      {/if}
    </div>
  </div>
{/if}
