<!--
  ResizablePanes — two-pane layout with a draggable divider.

  No resizable/splitter primitive existed anywhere in the codebase before
  this; this is a new, generic component (not DocLang-specific) usable
  anywhere two panes need to share space with a user-adjustable split.
  Nest two instances for a 3-pane layout (e.g. left | middle | right):

      <ResizablePanes id="outer" initialRatio={0.35}>
        {#snippet start()}...{/snippet}
        {#snippet end()}
          <ResizablePanes id="inner" initialRatio={0.5}>
            {#snippet start()}...{/snippet}
            {#snippet end()}...{/snippet}
          </ResizablePanes>
        {/snippet}
      </ResizablePanes>

  Usage notes:
  - `direction` picks the split axis. "horizontal" (default) splits left/right;
    "vertical" splits top/bottom.
  - `initialRatio` is the start pane's share of the total size (0-1).
  - `minSize` is a per-pane minimum in px, enforced on both panes.
  - Pass a stable `id` to persist the user's chosen ratio to localStorage
    across reloads; omit it to keep the ratio session-only.
-->
<script lang="ts">
  import { untrack } from "svelte";

  interface Props {
    direction?: "horizontal" | "vertical";
    initialRatio?: number;
    minSize?: number;
    id?: string;
    start?: import("svelte").Snippet;
    end?: import("svelte").Snippet;
  }

  let { direction = "horizontal", initialRatio = 0.5, minSize = 120, id, start, end }: Props = $props();
  // Only the STARTING value of initialRatio matters -- ratio becomes
  // user-controlled state from here on, not reactive to prop changes.
  const initialRatioValue = untrack(() => initialRatio);

  const STORAGE_PREFIX = "bimguard-resizable-panes:";

  function loadStoredRatio(): number | null {
    if (!id) return null;
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + id);
      const parsed = raw ? Number(raw) : NaN;
      return Number.isFinite(parsed) && parsed > 0 && parsed < 1 ? parsed : null;
    } catch {
      return null;
    }
  }

  function persistRatio(value: number) {
    if (!id) return;
    try {
      localStorage.setItem(STORAGE_PREFIX + id, String(value));
    } catch {
      // Best-effort only (private browsing, storage disabled, etc.)
    }
  }

  let ratio = $state(loadStoredRatio() ?? initialRatioValue);
  let containerEl: HTMLDivElement | undefined = $state();
  let dragging = $state(false);

  function clampRatio(next: number, totalSize: number): number {
    if (totalSize <= 0) return next;
    const minRatio = Math.min(0.5, minSize / totalSize);
    return Math.min(Math.max(next, minRatio), 1 - minRatio);
  }

  function updateFromPointer(clientX: number, clientY: number) {
    if (!containerEl) return;
    const rect = containerEl.getBoundingClientRect();
    const totalSize = direction === "horizontal" ? rect.width : rect.height;
    if (totalSize <= 0) return;
    const offset = direction === "horizontal" ? clientX - rect.left : clientY - rect.top;
    ratio = clampRatio(offset / totalSize, totalSize);
  }

  function onDividerPointerDown(e: PointerEvent) {
    dragging = true;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  function onDividerPointerMove(e: PointerEvent) {
    if (!dragging) return;
    updateFromPointer(e.clientX, e.clientY);
  }

  function onDividerPointerUp() {
    if (!dragging) return;
    dragging = false;
    persistRatio(ratio);
  }

  function onDividerKeydown(e: KeyboardEvent) {
    const step = e.shiftKey ? 0.1 : 0.02;
    const horizontal = direction === "horizontal";
    if ((horizontal && e.key === "ArrowLeft") || (!horizontal && e.key === "ArrowUp")) {
      ratio = clampRatio(ratio - step, containerSize());
      persistRatio(ratio);
      e.preventDefault();
    } else if ((horizontal && e.key === "ArrowRight") || (!horizontal && e.key === "ArrowDown")) {
      ratio = clampRatio(ratio + step, containerSize());
      persistRatio(ratio);
      e.preventDefault();
    }
  }

  function containerSize(): number {
    if (!containerEl) return 0;
    const rect = containerEl.getBoundingClientRect();
    return direction === "horizontal" ? rect.width : rect.height;
  }

  let startFlexBasis = $derived(`${(ratio * 100).toFixed(3)}%`);
</script>

<svelte:window
  onpointermove={dragging ? onDividerPointerMove : undefined}
  onpointerup={dragging ? onDividerPointerUp : undefined}
/>

<div
  bind:this={containerEl}
  class="flex min-h-0 min-w-0 flex-1 {direction === 'horizontal' ? 'flex-row' : 'flex-col'}"
>
  <div
    class="min-h-0 min-w-0 overflow-hidden"
    style="flex: 0 0 {startFlexBasis};"
  >
    {@render start?.()}
  </div>

  <!-- WAI-ARIA "window splitter" pattern: a focusable, keyboard-operable
       role="separator" is the documented accessible shape for a resizable
       divider (https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/). -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    role="separator"
    tabindex="0"
    aria-orientation={direction === "horizontal" ? "vertical" : "horizontal"}
    aria-label="Resize panes"
    onpointerdown={onDividerPointerDown}
    onkeydown={onDividerKeydown}
    class="group relative shrink-0 touch-none select-none {direction === 'horizontal'
      ? 'w-1 cursor-col-resize'
      : 'h-1 cursor-row-resize'} bg-slate-800/60 transition-colors hover:bg-accent focus-visible:bg-accent focus-visible:outline-hidden {dragging
      ? 'bg-accent'
      : ''}"
  ></div>

  <div class="min-h-0 min-w-0 flex-1 overflow-hidden">
    {@render end?.()}
  </div>
</div>
