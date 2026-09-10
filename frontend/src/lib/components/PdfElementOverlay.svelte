<!--
  PdfElementOverlay — per-element bbox overlay + reading-order arrows for one
  rendered PDF page. Generalizes the single-halo `activeBboxRect`/
  `slotBboxRects` pattern already in DocumentViewer.svelte (still used
  separately for the external rule-source-jump `bbox` prop) to N elements,
  hoverable/clickable, colored by kind.

  Reading-order arrows only connect elements ON THIS PAGE -- a transition to
  the next page is shown as a small arrow at the page edge rather than an
  (impossible, single-page-scoped) cross-page line.
-->
<script lang="ts">
  import type { DocumentElementBbox, DocumentElementKind } from "../types";
  import { cursorTooltip } from "../actions/cursorTooltip";

  interface Props {
    /** Every element on the document, pre-filtered by the caller isn't required -- this filters to `pageNumber` itself. */
    elements: DocumentElementBbox[];
    pageNumber: number;
    /** pdf.js PageViewport for the currently rendered page, for coordinate conversion. */
    viewport: any;
    /** Canvas pixel size this overlay must exactly match. */
    width: number;
    height: number;
    selectedElementId: string | null;
    onSelect: (elementId: string) => void;
    showBoxes?: boolean;
    showReadingOrder?: boolean;
  }

  let {
    elements,
    pageNumber,
    viewport,
    width,
    height,
    selectedElementId,
    onSelect,
    showBoxes = true,
    showReadingOrder = false,
  }: Props = $props();

  const KIND_COLOR: Record<DocumentElementKind, string> = {
    heading: "#a78bfa",
    paragraph: "#60a5fa",
    list: "#fb923c",
    table: "#4ade80",
    picture: "#f472b6",
  };

  interface OverlayBox {
    elementId: string;
    kind: DocumentElementKind;
    order: number;
    left: number;
    top: number;
    boxWidth: number;
    boxHeight: number;
    centerX: number;
    centerY: number;
  }

  function toViewportRect(bbox: NonNullable<DocumentElementBbox["bbox"]>): [number, number, number, number] | null {
    try {
      const minX = Math.min(bbox.l, bbox.r);
      const minY = Math.min(bbox.t, bbox.b);
      const maxX = Math.max(bbox.l, bbox.r);
      const maxY = Math.max(bbox.t, bbox.b);
      const [rx1, ry1, rx2, ry2] = viewport.convertToViewportRectangle([minX, minY, maxX, maxY]);
      return [Math.min(rx1, rx2), Math.min(ry1, ry2), Math.abs(rx2 - rx1), Math.abs(ry2 - ry1)];
    } catch {
      return null;
    }
  }

  let pageElements = $derived(
    elements
      .filter((el) => el.page_number === pageNumber && el.bbox)
      .sort((a, b) => a.order - b.order)
  );

  let boxes = $derived(
    pageElements.reduce<OverlayBox[]>((acc, el) => {
      const rect = el.bbox ? toViewportRect(el.bbox) : null;
      if (!rect) return acc;
      const [left, top, boxWidth, boxHeight] = rect;
      acc.push({
        elementId: el.element_id,
        kind: el.kind,
        order: el.order,
        left,
        top,
        boxWidth,
        boxHeight,
        centerX: left + boxWidth / 2,
        centerY: top + boxHeight / 2,
      });
      return acc;
    }, [])
  );

  let boxById = $derived(new Map(boxes.map((b) => [b.elementId, b])));

  // All elements globally (not just this page) in reading order, so we know
  // whether this page's last box's "next" element is on another page --
  // drawn as a small edge indicator rather than a same-page line.
  let orderedAll = $derived([...elements].sort((a, b) => a.order - b.order));

  interface ArrowSegment {
    key: string;
    x1: number;
    y1: number;
    x2: number;
    y2: number;
  }

  let readingOrderArrows = $derived.by((): ArrowSegment[] => {
    if (!showReadingOrder || boxes.length < 2) return [];
    const segments: ArrowSegment[] = [];
    for (let i = 0; i < boxes.length - 1; i++) {
      const a = boxes[i];
      const b = boxes[i + 1];
      segments.push({ key: `${a.elementId}->${b.elementId}`, x1: a.centerX, y1: a.centerY, x2: b.centerX, y2: b.centerY });
    }
    return segments;
  });

  /** True when this page's last visible box is immediately followed (globally) by an element on a different page. */
  let continuesToNextPage = $derived.by(() => {
    if (!showReadingOrder || boxes.length === 0) return false;
    const lastBox = boxes[boxes.length - 1];
    const idx = orderedAll.findIndex((el) => el.element_id === lastBox.elementId);
    const next = idx >= 0 ? orderedAll[idx + 1] : null;
    return Boolean(next && next.page_number !== pageNumber);
  });

  function kindLabel(kind: DocumentElementKind): string {
    return kind.charAt(0).toUpperCase() + kind.slice(1);
  }
</script>

{#if (showBoxes && boxes.length > 0) || readingOrderArrows.length > 0}
  <svg
    class="pointer-events-none absolute left-0 top-0 overflow-visible"
    width={Math.round(width)}
    height={Math.round(height)}
    viewBox="0 0 {Math.round(width)} {Math.round(height)}"
  >
    {#if readingOrderArrows.length > 0}
      <defs>
        <marker id="reading-order-arrowhead-{pageNumber}" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#94a3b8" />
        </marker>
      </defs>
      {#each readingOrderArrows as arrow (arrow.key)}
        <line
          x1={arrow.x1}
          y1={arrow.y1}
          x2={arrow.x2}
          y2={arrow.y2}
          stroke="#94a3b8"
          stroke-width="1.5"
          stroke-dasharray="5 4"
          marker-end="url(#reading-order-arrowhead-{pageNumber})"
          opacity="0.75"
        />
      {/each}
      {#if continuesToNextPage}
        {@const lastBox = boxes[boxes.length - 1]}
        <line
          x1={lastBox.centerX}
          y1={lastBox.centerY}
          x2={lastBox.centerX}
          y2={Math.min(height - 4, lastBox.centerY + 24)}
          stroke="#94a3b8"
          stroke-width="1.5"
          stroke-dasharray="2 3"
          marker-end="url(#reading-order-arrowhead-{pageNumber})"
          opacity="0.6"
        />
      {/if}
    {/if}

    {#if showBoxes}
      {#each boxes as box (box.elementId)}
        {@const color = KIND_COLOR[box.kind] ?? "#94a3b8"}
        {@const isSelected = box.elementId === selectedElementId}
        <rect
          x={box.left}
          y={box.top}
          width={box.boxWidth}
          height={box.boxHeight}
          rx="2"
          fill={color}
          fill-opacity={isSelected ? 0.28 : 0.08}
          stroke={color}
          stroke-width={isSelected ? 2.5 : 1.25}
          class="pointer-events-auto cursor-pointer transition-[fill-opacity,stroke-width] duration-100 hover:fill-opacity-20"
          onclick={() => onSelect(box.elementId)}
          onkeydown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect(box.elementId))}
          use:cursorTooltip={{ text: kindLabel(box.kind) }}
          role="button"
          tabindex="0"
          aria-label="{kindLabel(box.kind)} element"
        />
      {/each}
    {/if}
  </svg>
{/if}
