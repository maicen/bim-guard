<script lang="ts">
  import { untrack } from "svelte";
  import type { Component, ComponentType, Snippet } from "svelte";
  import { ChevronDown, ChevronRight, ChevronLeft, ChevronUp } from "lucide-svelte";

  interface Props {
    title: string;
    icon?: Component<any> | ComponentType<any> | null;
    /** Which edge this panel docks against — picks the collapse direction and chevron. */
    side?: "left" | "right" | "bottom";
    /** Persists collapse state (and width, if resizable) across reloads under this key. Omit to keep session-only. */
    id?: string;
    collapsed?: boolean;
    /** Adds a drag handle on the edge facing the center content to resize the panel's width (or height for `side="bottom"`). */
    resizable?: boolean;
    initialSize?: number;
    minSize?: number;
    maxSize?: number;
    headerExtra?: Snippet;
    children?: Snippet;
  }

  let {
    title,
    icon = null,
    side = "left",
    id,
    collapsed = $bindable(false),
    resizable = false,
    initialSize = 288,
    minSize = 200,
    maxSize = 520,
    headerExtra,
    children,
  }: Props = $props();

  const STORAGE_PREFIX = "bimguard-collapsible-panel:";

  function loadStored(suffix: string): string | null {
    if (!id) return null;
    try {
      return localStorage.getItem(STORAGE_PREFIX + id + suffix);
    } catch {
      return null;
    }
  }
  function persist(suffix: string, value: string) {
    if (!id) return;
    try {
      localStorage.setItem(STORAGE_PREFIX + id + suffix, value);
    } catch {
      // Best-effort only (private browsing, storage disabled, etc.)
    }
  }

  const storedCollapsed = loadStored(":collapsed");
  if (storedCollapsed !== null) collapsed = storedCollapsed === "1";

  function toggle() {
    collapsed = !collapsed;
    persist(":collapsed", collapsed ? "1" : "0");
  }

  const storedSize = loadStored(":size");
  // Only the STARTING value of initialSize matters -- size becomes
  // user-controlled state from here on, not reactive to prop changes.
  let size = $state(storedSize ? Number(storedSize) : untrack(() => initialSize));
  let dragging = $state(false);
  let dragStart = 0;
  let dragStartSize = 0;

  function clampSize(value: number) {
    return Math.min(Math.max(value, minSize), maxSize);
  }

  // Dragging toward the center content should always grow the panel,
  // regardless of which edge it's docked against.
  function signedDelta(delta: number) {
    if (side === "right") return -delta;
    if (side === "bottom") return -delta;
    return delta;
  }

  function onHandlePointerDown(e: PointerEvent) {
    dragging = true;
    dragStart = side === "bottom" ? e.clientY : e.clientX;
    dragStartSize = size;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    e.preventDefault();
  }
  function onHandlePointerMove(e: PointerEvent) {
    if (!dragging) return;
    const pos = side === "bottom" ? e.clientY : e.clientX;
    size = clampSize(dragStartSize + signedDelta(pos - dragStart));
  }
  function onHandlePointerUp() {
    if (!dragging) return;
    dragging = false;
    persist(":size", String(size));
  }
  function onHandleKeydown(e: KeyboardEvent) {
    const step = e.shiftKey ? 40 : 10;
    const horizontal = side !== "bottom";
    const growKey = side === "right" ? "ArrowLeft" : horizontal ? "ArrowRight" : "ArrowUp";
    const shrinkKey = side === "right" ? "ArrowRight" : horizontal ? "ArrowLeft" : "ArrowDown";
    if (e.key === growKey) {
      size = clampSize(size + step);
      persist(":size", String(size));
      e.preventDefault();
    } else if (e.key === shrinkKey) {
      size = clampSize(size - step);
      persist(":size", String(size));
      e.preventDefault();
    }
  }

  const Icon = $derived(icon);
  // Chevron points toward the direction expanding would go.
  const Chevron = $derived(
    side === "bottom" ? (collapsed ? ChevronUp : ChevronDown)
    : side === "right" ? (collapsed ? ChevronLeft : ChevronRight)
    : collapsed ? ChevronRight : ChevronLeft,
  );

  const showHandle = $derived(resizable && !collapsed);
</script>

<svelte:window
  onpointermove={dragging ? onHandlePointerMove : undefined}
  onpointerup={dragging ? onHandlePointerUp : undefined}
/>

<!-- For a left-docked panel the handle faces the center content, so it's
     the trailing sibling here (below); for right/bottom it's the leading one. -->
<div class="flex shrink-0 {side === 'bottom' ? 'flex-col' : 'flex-row'}">
  {#if showHandle && side !== "left" && side !== "bottom"}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      role="separator"
      tabindex="0"
      aria-orientation="vertical"
      aria-label="Resize {title} panel"
      onpointerdown={onHandlePointerDown}
      onkeydown={onHandleKeydown}
      class="group relative w-1 shrink-0 cursor-col-resize touch-none select-none bg-slate-800/60 transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none {dragging
        ? 'bg-accent'
        : ''}"
    ></div>
  {/if}

  <div
    class="flex min-h-0 min-w-0 flex-col overflow-hidden border-slate-800 bg-slate-900/60 {side ===
    'bottom'
      ? 'border-t'
      : side === 'right'
        ? 'border-l'
        : 'border-r'}"
    style:width={side !== "bottom" && showHandle ? `${size}px` : undefined}
    style:height={side === "bottom" && showHandle ? `${size}px` : undefined}
  >
    <div
      class="flex h-9 shrink-0 items-center justify-between gap-2 border-b border-slate-800/80 bg-slate-950/60 px-2.5"
    >
      <button
        type="button"
        onclick={toggle}
        class="flex min-w-0 flex-1 items-center gap-1.5 text-left text-xs font-semibold tracking-wide text-slate-200 hover:text-slate-50"
        aria-expanded={!collapsed}
      >
        {#if Icon}
          <Icon class="h-3.5 w-3.5 shrink-0 text-blue-400" />
        {/if}
        {#if !collapsed}
          <span class="truncate">{title}</span>
        {/if}
      </button>
      <div class="flex shrink-0 items-center gap-1">
        {#if !collapsed}
          {@render headerExtra?.()}
        {/if}
        <button
          type="button"
          onclick={toggle}
          class="rounded p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
          aria-label={collapsed ? `Expand ${title}` : `Collapse ${title}`}
          title={collapsed ? `Expand ${title}` : `Collapse ${title}`}
        >
          <Chevron class="h-3.5 w-3.5" />
        </button>
      </div>
    </div>

    <!-- Content stays mounted while collapsed (hidden via the `hidden` attribute,
         not removed with {#if}) so any DOM refs a child hands to the IFC engine
         (e.g. the Drawings panel's sheet-board host) stay valid regardless of
         collapse state instead of being torn down and never recreated. -->
    <div class="min-h-0 flex-1 overflow-y-auto" hidden={collapsed}>
      {@render children?.()}
    </div>
  </div>

  {#if showHandle && side === "left"}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      role="separator"
      tabindex="0"
      aria-orientation="vertical"
      aria-label="Resize {title} panel"
      onpointerdown={onHandlePointerDown}
      onkeydown={onHandleKeydown}
      class="group relative w-1 shrink-0 cursor-col-resize touch-none select-none bg-slate-800/60 transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none {dragging
        ? 'bg-accent'
        : ''}"
    ></div>
  {/if}

  {#if showHandle && side === "bottom"}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      role="separator"
      tabindex="0"
      aria-orientation="horizontal"
      aria-label="Resize {title} panel"
      onpointerdown={onHandlePointerDown}
      onkeydown={onHandleKeydown}
      class="group relative h-1 w-full shrink-0 cursor-row-resize touch-none select-none bg-slate-800/60 transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-none {dragging
        ? 'bg-accent'
        : ''}"
    ></div>
  {/if}
</div>
