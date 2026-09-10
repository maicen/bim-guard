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

  export type ElementLayer = "body" | "furniture" | "background";

  export interface ArrowStyle {
    color: string;
    width: number;
    head: number;
    style: "solid" | "dashed" | "dotted";
  }

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
    /** Per-element DocLang `<layer>` classification (body/furniture/background), keyed by element_id -- elements missing here default to "body". */
    elementLayers?: Map<string, ElementLayer>;
    /** Small numbered chip at each box's corner, showing its document reading order. */
    showBadges?: boolean;
    arrowStyle?: ArrowStyle;
    /** Richer per-element tooltip text (layer/caption/etc.); falls back to the kind label when omitted. */
    tooltipText?: (elementId: string) => string | null;
  }

  const DEFAULT_ARROW_STYLE: ArrowStyle = { color: "#94a3b8", width: 1.5, head: 6, style: "dashed" };

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
    elementLayers,
    showBadges = false,
    arrowStyle = DEFAULT_ARROW_STYLE,
    tooltipText,
  }: Props = $props();

  function dashArrayFor(style: ArrowStyle["style"], width: number): string | null {
    if (style === "dashed") return `${(width * 3.3).toFixed(1)} ${(width * 2.7).toFixed(1)}`;
    if (style === "dotted") return `${width.toFixed(1)} ${(width * 2).toFixed(1)}`;
    return null;
  }

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
    layer: ElementLayer;
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
        layer: elementLayers?.get(el.element_id) ?? "body",
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
      {@const dash = dashArrayFor(arrowStyle.style, arrowStyle.width)}
      <defs>
        <marker
          id="reading-order-arrowhead-{pageNumber}"
          markerWidth={arrowStyle.head}
          markerHeight={arrowStyle.head}
          refX={arrowStyle.head * 0.75}
          refY={arrowStyle.head / 2}
          orient="auto"
        >
          <path d="M0,0 L{arrowStyle.head * 0.75},{arrowStyle.head / 2} L0,{arrowStyle.head} Z" fill={arrowStyle.color} />
        </marker>
      </defs>
      {#each readingOrderArrows as arrow (arrow.key)}
        <line
          x1={arrow.x1}
          y1={arrow.y1}
          x2={arrow.x2}
          y2={arrow.y2}
          stroke={arrowStyle.color}
          stroke-width={arrowStyle.width}
          stroke-dasharray={dash}
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
          stroke={arrowStyle.color}
          stroke-width={arrowStyle.width}
          stroke-dasharray={dash ?? "2 3"}
          marker-end="url(#reading-order-arrowhead-{pageNumber})"
          opacity="0.6"
        />
      {/if}
    {/if}

    {#if showBoxes}
      {#if boxes.some((b) => b.layer !== "body")}
        <defs>
          <pattern id="layer-hatch-{pageNumber}" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <rect width="6" height="6" fill="transparent" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#94a3b8" stroke-width="2" opacity="0.35" />
          </pattern>
        </defs>
      {/if}
      {#each boxes as box (box.elementId)}
        {@const color = KIND_COLOR[box.kind] ?? "#94a3b8"}
        {@const isSelected = box.elementId === selectedElementId}
        {@const isLayered = box.layer !== "body"}
        <rect
          x={box.left}
          y={box.top}
          width={box.boxWidth}
          height={box.boxHeight}
          rx="2"
          fill={isLayered ? `url(#layer-hatch-${pageNumber})` : color}
          fill-opacity={isLayered ? 1 : isSelected ? 0.28 : 0.08}
          stroke={color}
          stroke-width={isSelected ? 2.5 : 1.25}
          stroke-dasharray={isLayered ? "3 2" : undefined}
          class="pointer-events-auto cursor-pointer transition-[fill-opacity,stroke-width] duration-100 hover:fill-opacity-20"
          onclick={() => onSelect(box.elementId)}
          onkeydown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect(box.elementId))}
          use:cursorTooltip={{ text: [kindLabel(box.kind), tooltipText?.(box.elementId)].filter(Boolean).join("\n") }}
          role="button"
          tabindex="0"
          aria-label="{kindLabel(box.kind)} element"
        />
      {/each}
      {#if showBadges}
        {#each boxes as box (`badge-${box.elementId}`)}
          {@const color = KIND_COLOR[box.kind] ?? "#94a3b8"}
          <g class="pointer-events-none">
            <circle cx={box.left + 7} cy={box.top + 7} r="7" fill={color} opacity="0.92" />
            <text
              x={box.left + 7}
              y={box.top + 7}
              text-anchor="middle"
              dominant-baseline="central"
              font-size="8"
              font-weight="700"
              fill="#0f172a"
            >
              {box.order + 1}
            </text>
          </g>
        {/each}
      {/if}
    {/if}
  </svg>
{/if}
