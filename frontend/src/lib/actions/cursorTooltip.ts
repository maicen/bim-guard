import { portal } from "./portal";

interface CursorTooltipOptions {
  /** Tooltip text. Empty/falsy disables the tooltip entirely. */
  text?: string | null;
  /** Gap in px between the cursor and the tooltip. */
  offset?: number;
}

const EDGE_PADDING = 8;

/**
 * Attaches a small floating tooltip that follows the live pointer position
 * (not a fixed trigger rect, unlike HoverCard) and clamps to the viewport.
 * An action rather than a wrapping component so it never changes the host
 * element's DOM structure — safe to attach to XML fold toggles, bbox overlay
 * boxes, or anything else that can't tolerate an extra wrapper.
 *
 * Usage: <button use:cursorTooltip={{ text: "Collapse" }}>...</button>
 * Works on SVG elements too (e.g. a bbox overlay <rect>), hence the Element type.
 */
export function cursorTooltip(node: Element, options: CursorTooltipOptions = {}) {
  let opts = options;
  let tooltipEl: HTMLDivElement | null = null;
  let destroyPortal: (() => void) | null = null;

  function place(clientX: number, clientY: number) {
    if (!tooltipEl) return;
    const offset = opts.offset ?? 12;
    const rect = tooltipEl.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let left = clientX + offset;
    let top = clientY + offset;

    if (left + rect.width + EDGE_PADDING > vw) left = clientX - offset - rect.width;
    if (top + rect.height + EDGE_PADDING > vh) top = clientY - offset - rect.height;
    left = Math.min(Math.max(EDGE_PADDING, left), Math.max(EDGE_PADDING, vw - rect.width - EDGE_PADDING));
    top = Math.min(Math.max(EDGE_PADDING, top), Math.max(EDGE_PADDING, vh - rect.height - EDGE_PADDING));

    tooltipEl.style.left = `${Math.round(left)}px`;
    tooltipEl.style.top = `${Math.round(top)}px`;
  }

  function show(e: PointerEvent) {
    if (!opts.text) return;
    if (!tooltipEl) {
      tooltipEl = document.createElement("div");
      tooltipEl.setAttribute("role", "tooltip");
      tooltipEl.className =
        "pointer-events-none fixed z-[70] max-w-64 whitespace-pre-line rounded-md border border-slate-800 bg-slate-900/95 px-2 py-1 text-micro text-slate-200 shadow-lg shadow-black/30 backdrop-blur-sm";
      destroyPortal = portal(tooltipEl).destroy;
    }
    tooltipEl.textContent = opts.text;
    place(e.clientX, e.clientY);
  }

  function move(e: PointerEvent) {
    if (!tooltipEl) return;
    place(e.clientX, e.clientY);
  }

  function hide() {
    if (tooltipEl) {
      destroyPortal?.();
      tooltipEl = null;
      destroyPortal = null;
    }
  }

  node.addEventListener("pointerenter", show);
  node.addEventListener("pointermove", move);
  node.addEventListener("pointerleave", hide);
  node.addEventListener("pointerdown", hide);

  return {
    update(newOptions: CursorTooltipOptions) {
      opts = newOptions;
      if (!opts.text) hide();
      else if (tooltipEl) tooltipEl.textContent = opts.text;
    },
    destroy() {
      node.removeEventListener("pointerenter", show);
      node.removeEventListener("pointermove", move);
      node.removeEventListener("pointerleave", hide);
      node.removeEventListener("pointerdown", hide);
      hide();
    },
  };
}
