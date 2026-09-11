<script lang="ts">
  import { onMount, onDestroy, tick } from "svelte";
  import {
    ChevronLeft,
    ChevronRight,
    AlertCircle,
    ZoomIn,
    ZoomOut,
    RotateCcw,
    Rows3,
    FileText as FileIcon,
    FileCode,
    Download,
    Copy,
    Check,
    Settings2,
    ChevronDown,
  } from "lucide-svelte";
  import { documentsApi } from "../api";
  import { authHeaders, withAuthToken } from "../authToken";
  import type { DocumentElementBbox } from "../types";
  import LoadingState from "./LoadingState.svelte";
  import EmptyState from "./EmptyState.svelte";
  import DocLangXmlTree from "./DocLangXmlTree.svelte";
  import PdfElementOverlay from "./PdfElementOverlay.svelte";
  import type { ElementLayer, ArrowStyle } from "./PdfElementOverlay.svelte";

  interface Props {
    documentId: number;
    /** 1-based page to open on, when known (from GET /api/rules/{id}/source). */
    page?: number | null;
    /** Source snippet to highlight — matched against the PDF text layer, or the plain-text panel for non-PDF documents. */
    highlightText?: string | null;
    /** Bounding box coordinates {l, t, r, b, coord_origin} on the page for visual halo highlighting. */
    bbox?: { l: number; t: number; r: number; b: number; coord_origin?: string } | null;
  }

  let { documentId, page = null, highlightText = null, bbox = null }: Props = $props();

  // Single-page mode DOM refs
  let textLayerEl: HTMLDivElement = $state();
  let canvasEl: HTMLCanvasElement = $state();
  let textPanelEl: HTMLDivElement = $state();
  // Continuous mode DOM refs
  let scrollContainerEl: HTMLDivElement = $state();

  let loading = $state(true);
  let error: string | null = $state(null);
  let isPdf = $state(false);
  let plainText = $state("");
  let filename = $state("");
  /** Set when a PDF failed to parse (e.g. corrupted xref/trailer) and we fell back to the text panel. */
  let pdfFallbackNotice: string | null = $state(null);
  /** Set when the background fetch for DocLang XML/text (PDF path only) fails, so it isn't silently swallowed. */
  let doclangLoadError: string | null = $state(null);

  let pdfDoc: any = $state(null);
  let currentPage = $state(1);
  let pageCount = $state(0);
  let pageInputValue = $state("1");
  let renderTask: any = null;

  const DEFAULT_SCALE = 1.25;
  const MIN_SCALE = 0.5;
  const MAX_SCALE = 3;
  const SCALE_STEP = 0.25;
  const RENDER_TIMEOUT_MS = 20000;

  let scale = $state(DEFAULT_SCALE);
  let viewMode: "single" | "continuous" = $state("single");

  // Continuous mode: one lazily-rendered "slot" per page, virtualized via
  // IntersectionObserver so a 300+ page document never renders every page's
  // canvas at once (each rendered page is several MB — rendering all of them
  // for a large document would exhaust tab memory).
  interface PageSlot {
    pageNumber: number;
    rendered: boolean;
  }
  let pageSlots: PageSlot[] = $state([]);
  let pageSlotEls: (HTMLDivElement | undefined)[] = $state([]);
  let pageCanvasEls: (HTMLCanvasElement | undefined)[] = $state([]);
  let pageTextLayerEls: (HTMLDivElement | undefined)[] = $state([]);
  let estimatedPageWidth = $state(0);
  let estimatedPageHeight = $state(0);
  let intersectionObserver: IntersectionObserver | null = null;
  // Bumped on scale/mode change so an in-flight render from a stale
  // scale/mode can detect it's obsolete and bail without clobbering state.
  let renderGeneration = 0;

  let activeBboxRect: { left: number; top: number; width: number; height: number } | null = $state(null);
  let slotBboxRects: Record<number, { left: number; top: number; width: number; height: number }> = $state({});

  // Per-element bbox overlay (feature: hover/click any paragraph/heading/
  // table/picture, not just the single external rule-source halo above).
  let elementBboxes: DocumentElementBbox[] = $state([]);
  let showBboxOverlay = $state(true);
  let showReadingOrderArrows = $state(false);
  let showElementBadges = $state(false);
  let currentPageViewport: any = $state(null);
  let slotViewports: Record<number, any> = $state({});

  // Reading-order arrow appearance -- persisted so a user's chosen style
  // survives across documents and sessions instead of resetting each load.
  const OVERLAY_PREFS_KEY = "bimguard_document_viewer_overlay_prefs";
  interface OverlayPrefs {
    showBadges: boolean;
    arrowColor: string;
    arrowWidth: number;
    arrowHead: number;
    arrowStyle: "solid" | "dashed" | "dotted";
  }
  const DEFAULT_OVERLAY_PREFS: OverlayPrefs = {
    showBadges: false,
    arrowColor: "#94a3b8",
    arrowWidth: 1.5,
    arrowHead: 6,
    arrowStyle: "dashed",
  };
  let arrowColor = $state(DEFAULT_OVERLAY_PREFS.arrowColor);
  let arrowWidth = $state(DEFAULT_OVERLAY_PREFS.arrowWidth);
  let arrowHead = $state(DEFAULT_OVERLAY_PREFS.arrowHead);
  let arrowLineStyle: OverlayPrefs["arrowStyle"] = $state(DEFAULT_OVERLAY_PREFS.arrowStyle);
  let arrowStyleValue: ArrowStyle = $derived({
    color: arrowColor,
    width: arrowWidth,
    head: arrowHead,
    style: arrowLineStyle,
  });
  let overlaySettingsOpen = $state(false);
  let overlayPrefsLoaded = false;

  function loadOverlayPrefs() {
    try {
      const raw = localStorage.getItem(OVERLAY_PREFS_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Partial<OverlayPrefs>;
      showElementBadges = parsed.showBadges ?? DEFAULT_OVERLAY_PREFS.showBadges;
      arrowColor = parsed.arrowColor ?? DEFAULT_OVERLAY_PREFS.arrowColor;
      arrowWidth = parsed.arrowWidth ?? DEFAULT_OVERLAY_PREFS.arrowWidth;
      arrowHead = parsed.arrowHead ?? DEFAULT_OVERLAY_PREFS.arrowHead;
      arrowLineStyle = parsed.arrowStyle ?? DEFAULT_OVERLAY_PREFS.arrowStyle;
    } catch {
      // ignore -- fall back to defaults
    } finally {
      overlayPrefsLoaded = true;
    }
  }

  $effect(() => {
    // Re-runs on every pref change; skipped until the initial load above has
    // run once, so it never clobbers a saved pref with the module defaults.
    const prefs: OverlayPrefs = {
      showBadges: showElementBadges,
      arrowColor,
      arrowWidth,
      arrowHead,
      arrowStyle: arrowLineStyle,
    };
    if (!overlayPrefsLoaded) return;
    try {
      localStorage.setItem(OVERLAY_PREFS_KEY, JSON.stringify(prefs));
    } catch {
      // ignore -- persistence is a nicety, not a requirement
    }
  });

  // Drag-to-pan (single-page mode only -- continuous mode's primary gesture
  // is already vertical scroll-to-flip-page via initPageWheelNav-equivalent
  // logic below, and panning there would fight it). Only engages when the
  // drag starts on empty canvas background, never on the PDF text layer or
  // a bbox-overlay box, so text selection and element click-to-select both
  // keep working exactly as before.
  let singlePageScrollEl: HTMLDivElement | undefined = $state();
  const PAN_DRAG_THRESHOLD_PX = 4;
  let panDrag: {
    pointerId: number;
    startX: number;
    startY: number;
    scrollLeft: number;
    scrollTop: number;
    moved: boolean;
  } | null = $state(null);

  function isPannableTarget(target: EventTarget | null): boolean {
    if (!(target instanceof Element)) return true;
    return !target.closest(".pdf-text-layer, svg");
  }

  function onPanPointerDown(e: PointerEvent, container: HTMLDivElement | undefined) {
    if (e.button !== 0 || !container || !isPannableTarget(e.target)) return;
    panDrag = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      scrollLeft: container.scrollLeft,
      scrollTop: container.scrollTop,
      moved: false,
    };
  }

  function onPanPointerMove(e: PointerEvent) {
    if (!panDrag || e.pointerId !== panDrag.pointerId || !singlePageScrollEl) return;
    const dx = e.clientX - panDrag.startX;
    const dy = e.clientY - panDrag.startY;
    if (!panDrag.moved) {
      if (Math.hypot(dx, dy) < PAN_DRAG_THRESHOLD_PX) return;
      panDrag.moved = true;
      singlePageScrollEl.setPointerCapture(e.pointerId);
    }
    singlePageScrollEl.scrollLeft = panDrag.scrollLeft - dx;
    singlePageScrollEl.scrollTop = panDrag.scrollTop - dy;
    e.preventDefault();
  }

  function onPanPointerUp(e: PointerEvent) {
    if (!panDrag || e.pointerId !== panDrag.pointerId) return;
    if (panDrag.moved && singlePageScrollEl?.hasPointerCapture(e.pointerId)) {
      singlePageScrollEl.releasePointerCapture(e.pointerId);
    }
    panDrag = null;
  }

  let isPanning = $derived(panDrag?.moved ?? false);

  let doclangXml = $state("");
  // Original Page / DocLang / Reading View render simultaneously as three
  // synchronized panes (rather than switching between them) -- these control
  // per-pane visibility via the "Views" menu, mirroring the reference
  // DocLang Viewer. All default on; a document with no DocLang XML at all
  // just shows Original Page, full width (see the {#if doclangXml} branch
  // in the template).
  let showOriginalPage = $state(true);
  let showDoclangPane = $state(true);
  let showReadingPane = $state(true);
  let viewsMenuOpen = $state(false);
  let layersMenuOpen = $state(false);
  // Shared across the rendered-blocks view, the XML tree, and the bbox
  // overlay -- clicking any one of them highlights/scrolls the others to
  // the same DocLang-injected element id (feature: click-to-sync selection).
  let selectedElementId: string | null = $state(null);

  function selectElement(elementId: string | null) {
    selectedElementId = elementId;
  }
  let copiedXml = $state(false);

  function copyXmlToClipboard() {
    if (!doclangXml) return;
    navigator.clipboard.writeText(doclangXml);
    copiedXml = true;
    setTimeout(() => {
      copiedXml = false;
    }, 2500);
  }

  function downloadDoclangArchive() {
    window.open(withAuthToken(documentsApi.getExportDoclangUrl(documentId)), "_blank");
  }

  interface ParsedOtslTable {
    title: string;
    rows: string[][];
  }

  /** Parse a single OTSL <table> element's <fcel/>/<nl/> grid into rows of cell text. */
  function extractOtslRows(tableNode: Element): string[][] {
    const rows: string[][] = [];
    let currentRow: string[] = [];
    let currentCellParts: string[] = [];

    for (let i = 0; i < tableNode.childNodes.length; i++) {
      const node = tableNode.childNodes[i];
      if (node.nodeType === Node.ELEMENT_NODE) {
        const el = node as HTMLElement;
        const tag = el.tagName.toLowerCase();
        if (tag === "fcel") {
          if (currentCellParts.length > 0) {
            const text = currentCellParts.join(" ").trim();
            if (text) currentRow.push(text);
            currentCellParts = [];
          }
          const inner = el.textContent?.trim();
          if (inner) currentCellParts.push(inner);
        } else if (tag === "nl") {
          if (currentCellParts.length > 0) {
            const text = currentCellParts.join(" ").trim();
            if (text) currentRow.push(text);
            currentCellParts = [];
          }
          if (currentRow.length > 0) {
            rows.push(currentRow);
            currentRow = [];
          }
        } else {
          const text = el.textContent?.trim();
          if (text) currentCellParts.push(text);
        }
      } else if (node.nodeType === Node.TEXT_NODE) {
        const text = node.textContent?.trim();
        if (text) currentCellParts.push(text);
      }
    }
    if (currentCellParts.length > 0) {
      const text = currentCellParts.join(" ").trim();
      if (text) currentRow.push(text);
    }
    if (currentRow.length > 0) {
      rows.push(currentRow);
    }

    return rows.filter((r) => r.some((c) => c.trim()));
  }

  function parseDoclangTables(xml: string): ParsedOtslTable[] {
    if (!xml) return [];
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(xml, "application/xml");
      const tableNodes = Array.from(doc.querySelectorAll("table"));
      return tableNodes.map((tableNode, idx) => {
        let title = `Table ${idx + 1}`;
        let prev = tableNode.previousElementSibling;
        while (prev) {
          if (prev.tagName.toLowerCase() === "heading") {
            title = prev.textContent?.trim() || title;
            break;
          }
          prev = prev.previousElementSibling;
        }
        return { title, rows: extractOtslRows(tableNode) };
      });
    } catch {
      return [];
    }
  }

  let parsedTables = $derived(parseDoclangTables(doclangXml));

  type DoclangBlock =
    | { type: "heading"; level: number; text: string; elementId: string | null; layer: ElementLayer }
    | { type: "paragraph"; text: string; elementId: string | null; layer: ElementLayer }
    | { type: "list"; items: string[] }
    | { type: "table"; title: string; rows: string[][]; elementId: string | null; layer: ElementLayer }
    | { type: "image"; src: string; alt: string; elementId: string | null; layer: ElementLayer }
    | { type: "page-break"; pageNumber: number };

  /**
   * Read the id BIM-Guard's backend injects into DocLang XML at extraction
   * time (`<custom><bg_element_id value="elem-N"/></custom>`, a direct child
   * -- see app/modules/document_parsing/doclang_element_ids.py). The value
   * lives on an attribute of a leaf element, never as text content, so it
   * never leaks into `textContent`-based text extraction elsewhere in this
   * file. Returns null for elements from documents predating this feature.
   */
  function getInjectedElementId(el: Element): string | null {
    for (const child of Array.from(el.children)) {
      if (child.tagName.toLowerCase() !== "custom") continue;
      for (const grandchild of Array.from(child.children)) {
        if (grandchild.tagName.toLowerCase() === "bg_element_id") {
          return grandchild.getAttribute("value");
        }
      }
    }
    return null;
  }

  /** Read a DocLang element's direct `<tag>` head child (label/layer/caption/xref/thread/...), if present. */
  function headChild(el: Element, tag: string): Element | null {
    for (const child of Array.from(el.children)) {
      if (child.tagName.toLowerCase() === tag) return child;
    }
    return null;
  }

  /** DocLang's `<layer value="body|furniture|background"/>` head child -- defaults to "body" when absent. */
  function getElementLayer(el: Element): ElementLayer {
    const value = headChild(el, "layer")?.getAttribute("value");
    return value === "furniture" || value === "background" ? value : "body";
  }

  interface ElementHeadMeta {
    layer: ElementLayer;
    label: string | null;
    caption: string | null;
    hasXref: boolean;
    hasThread: boolean;
  }

  /**
   * Per-element DocLang head metadata (layer/label/caption/xref/thread),
   * keyed by the same injected element_id used for bbox pairing -- built for
   * the PDF pane's overlay (layer hatching, richer hover tooltips) and the
   * DocLang reading view's Furniture/Background layer toggles.
   */
  function buildElementMeta(xml: string): Map<string, ElementHeadMeta> {
    const meta = new Map<string, ElementHeadMeta>();
    if (!xml) return meta;
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(xml, "application/xml");
      if (doc.querySelector("parsererror") || !doc.documentElement) return meta;
      const walker = document.createTreeWalker(doc.documentElement, NodeFilter.SHOW_ELEMENT);
      let node = walker.nextNode() as Element | null;
      while (node) {
        const id = getInjectedElementId(node);
        if (id) {
          meta.set(id, {
            layer: getElementLayer(node),
            label: headChild(node, "label")?.getAttribute("value") || null,
            caption: headChild(node, "caption")?.textContent?.trim() || null,
            hasXref: Boolean(headChild(node, "xref")),
            hasThread: Boolean(headChild(node, "thread")),
          });
        }
        node = walker.nextNode() as Element | null;
      }
    } catch {
      // best-effort enrichment only
    }
    return meta;
  }

  let elementMeta = $derived(buildElementMeta(doclangXml));
  let elementLayerMap = $derived(
    new Map<string, ElementLayer>(Array.from(elementMeta, ([id, m]) => [id, m.layer]))
  );

  function elementTooltipText(elementId: string): string | null {
    const meta = elementMeta.get(elementId);
    if (!meta) return null;
    const lines: string[] = [];
    if (meta.label) lines.push(meta.label);
    if (meta.layer !== "body") lines.push(`Layer: ${meta.layer}`);
    if (meta.caption) lines.push(`Caption: ${meta.caption}`);
    if (meta.hasXref) lines.push("Has cross-reference");
    if (meta.hasThread) lines.push("Part of a fragmented thread");
    return lines.length > 0 ? lines.join("\n") : null;
  }

  /** Read <picture><src uri="assets/..."/></picture>'s uri, resolved to a servable asset URL. */
  function pictureSrcUrl(pictureEl: Element): string | null {
    for (const child of Array.from(pictureEl.children)) {
      if (child.tagName.toLowerCase() !== "src") continue;
      const uri = child.getAttribute("uri");
      if (!uri) continue;
      if (/^(data:|https?:)/i.test(uri)) return uri;
      const filename = uri.replace(/^assets\//, "");
      return withAuthToken(documentsApi.getAssetUrl(documentId, filename));
    }
    return null;
  }

  function pictureCaption(pictureEl: Element): string {
    for (const child of Array.from(pictureEl.children)) {
      if (child.tagName.toLowerCase() === "caption") return child.textContent?.trim() || "";
    }
    return "";
  }

  /**
   * Walk the full DocLang XML tree in document order and produce a flat,
   * readable sequence of blocks (headings, paragraphs, lists, tables,
   * pictures) — the same tag set app/modules/document_parsing/doclang_chunker.py
   * handles on the backend — instead of extracting only the <table> elements.
   */
  function parseDoclangDocument(xml: string): DoclangBlock[] {
    if (!xml) return [];
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(xml, "application/xml");
      if (doc.querySelector("parsererror")) return [];
      const root = doc.documentElement;
      if (!root) return [];

      const blocks: DoclangBlock[] = [];
      const skip = new Set<Element>();
      let pendingListItems: string[] = [];
      let tableIdx = 0;
      let pageNumber = 1;

      const flushList = () => {
        if (pendingListItems.length > 0) {
          blocks.push({ type: "list", items: pendingListItems });
          pendingListItems = [];
        }
      };

      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
      let node = walker.nextNode() as Element | null;
      while (node) {
        if (skip.has(node)) {
          node = walker.nextNode() as Element | null;
          continue;
        }
        const tag = node.tagName.toLowerCase();

        if (tag === "heading") {
          flushList();
          const text = node.textContent?.trim() || "";
          if (text) {
            const levelAttr = parseInt(node.getAttribute("level") || "1", 10);
            const level = Number.isFinite(levelAttr) ? Math.min(Math.max(levelAttr, 1), 6) : 1;
            blocks.push({ type: "heading", level, text, elementId: getInjectedElementId(node), layer: getElementLayer(node) });
          }
        } else if (tag === "table") {
          flushList();
          tableIdx += 1;
          blocks.push({
            type: "table",
            title: `Table ${tableIdx}`,
            rows: extractOtslRows(node),
            elementId: getInjectedElementId(node),
            layer: getElementLayer(node),
          });
          node.querySelectorAll("*").forEach((descendant) => skip.add(descendant));
        } else if (tag === "picture") {
          flushList();
          const src = pictureSrcUrl(node);
          if (src) {
            blocks.push({
              type: "image",
              src,
              alt: pictureCaption(node),
              elementId: getInjectedElementId(node),
              layer: getElementLayer(node),
            });
          }
          node.querySelectorAll("*").forEach((descendant) => skip.add(descendant));
        } else if (tag === "text" || tag === "paragraph" || tag === "p") {
          flushList();
          const text = node.textContent?.trim() || "";
          if (text) blocks.push({ type: "paragraph", text, elementId: getInjectedElementId(node), layer: getElementLayer(node) });
        } else if (tag === "item" || tag === "li") {
          const text = node.textContent?.trim() || "";
          if (text) pendingListItems.push(text);
        } else if (tag === "page_break") {
          flushList();
          pageNumber += 1;
          // Only a divider between pages that both have content -- a
          // page_break before anything's been pushed yet (or two in a row)
          // would render a bare "Page N" heading with nothing above it.
          if (blocks.length > 0 && blocks[blocks.length - 1].type !== "page-break") {
            blocks.push({ type: "page-break", pageNumber });
          }
        }
        node = walker.nextNode() as Element | null;
      }
      flushList();
      return blocks;
    } catch {
      return [];
    }
  }

  let documentBlocks = $derived(parseDoclangDocument(doclangXml));

  // Reading view "Layers" toggles (DocLang's body/furniture/background
  // classification) -- both default to shown, matching the reference DocLang
  // Viewer's defaults, and are persisted alongside the PDF pane's overlay
  // prefs below.
  let showReadingFurniture = $state(true);
  let showReadingBackground = $state(true);
  let readingBlocks = $derived(
    documentBlocks.filter((b) => {
      if (!("layer" in b)) return true;
      if (b.layer === "furniture" && !showReadingFurniture) return false;
      if (b.layer === "background" && !showReadingBackground) return false;
      return true;
    })
  );

  // The "rendered" DocLang tab is windowed rather than mounting every block
  // at once -- a large specification can produce thousands of heading/
  // paragraph/table blocks, and Svelte still has to create + diff a DOM node
  // per block. BLOCKS_PAGE_SIZE more are appended each time the sentinel at
  // the bottom of the rendered list scrolls into view.
  const BLOCKS_PAGE_SIZE = 150;
  let visibleBlockCount = $state(BLOCKS_PAGE_SIZE);
  let visibleBlocks = $derived(readingBlocks.slice(0, visibleBlockCount));
  let blocksSentinelEl: HTMLDivElement | undefined = $state();
  let blocksObserver: IntersectionObserver | null = null;

  $effect(() => {
    // Re-run whenever the filtered block list itself changes (new document,
    // tab reopened, or a layer toggle flipped) so the window resets to the
    // first page instead of staying wherever it was left.
    void readingBlocks;
    visibleBlockCount = BLOCKS_PAGE_SIZE;
  });

  $effect(() => {
    blocksObserver?.disconnect();
    if (!blocksSentinelEl || readingBlocks.length <= visibleBlockCount) return;
    blocksObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          visibleBlockCount = Math.min(visibleBlockCount + BLOCKS_PAGE_SIZE, readingBlocks.length);
        }
      },
      { rootMargin: "400px" }
    );
    blocksObserver.observe(blocksSentinelEl);
    return () => blocksObserver?.disconnect();
  });

  // Cross-pane sync: when selection changes (from the XML tree or the bbox
  // overlay, not a click inside this pane itself) and the Reading View pane
  // is visible, scroll the matching block into view -- expanding the
  // windowed list first if the block hasn't been rendered yet.
  $effect(() => {
    const id = selectedElementId;
    if (!id || !showReadingPane) return;
    const blockIdx = readingBlocks.findIndex((b) => "elementId" in b && b.elementId === id);
    if (blockIdx === -1) return;
    if (blockIdx >= visibleBlockCount) {
      visibleBlockCount = Math.min(blockIdx + BLOCKS_PAGE_SIZE, readingBlocks.length);
    }
    tick().then(() => {
      document
        .querySelector(`[data-element-id="${CSS.escape(id)}"]`)
        ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });

  function updateBboxOverlay(viewport: any, pageNum: number) {
    if (!bbox || (page !== null && page !== pageNum)) {
      activeBboxRect = null;
      return;
    }
    try {
      const minX = Math.min(bbox.l, bbox.r);
      const minY = Math.min(bbox.t, bbox.b);
      const maxX = Math.max(bbox.l, bbox.r);
      const maxY = Math.max(bbox.t, bbox.b);
      const [rx1, ry1, rx2, ry2] = viewport.convertToViewportRectangle([minX, minY, maxX, maxY]);
      activeBboxRect = {
        left: Math.min(rx1, rx2),
        top: Math.min(ry1, ry2),
        width: Math.abs(rx2 - rx1),
        height: Math.abs(ry2 - ry1),
      };
    } catch {
      activeBboxRect = null;
    }
  }

  function updateSlotBboxOverlay(viewport: any, pageNum: number) {
    if (!bbox || (page !== null && page !== pageNum)) {
      delete slotBboxRects[pageNum];
      return;
    }
    try {
      const minX = Math.min(bbox.l, bbox.r);
      const minY = Math.min(bbox.t, bbox.b);
      const maxX = Math.max(bbox.l, bbox.r);
      const maxY = Math.max(bbox.t, bbox.b);
      const [rx1, ry1, rx2, ry2] = viewport.convertToViewportRectangle([minX, minY, maxX, maxY]);
      slotBboxRects[pageNum] = {
        left: Math.min(rx1, rx2),
        top: Math.min(ry1, ry2),
        width: Math.abs(rx2 - rx1),
        height: Math.abs(ry2 - ry1),
      };
    } catch {
      delete slotBboxRects[pageNum];
    }
  }

  let loadedDocumentId: number | null = null;

  async function load() {
    if (loadedDocumentId === documentId) return;
    loadedDocumentId = documentId;
    loading = true;
    error = null;
    pdfFallbackNotice = null;
    doclangLoadError = null;
    pdfDoc = null;
    isPdf = false;
    plainText = "";
    doclangXml = "";
    viewMode = "single";
    scale = DEFAULT_SCALE;
    teardownObserver();
    pageSlots = [];
    elementBboxes = [];
    selectedElementId = null;

    // Fetch document details in background to capture doclang_xml and text
    documentsApi
      .get(documentId)
      .then((detail) => {
        plainText = detail.text || "";
        doclangXml = detail.doclang_xml || "";
      })
      .catch((err: any) => {
        doclangLoadError = err?.message || "Failed to load DocLang content for this document.";
        console.warn("Background DocLang fetch failed", err);
      });

    // Per-element bbox overlay data -- best-effort, non-blocking: documents
    // predating this feature (or imported as raw .dclg/.dclx) just get an
    // empty list back and the overlay silently doesn't render.
    documentsApi
      .getElementBboxes(documentId)
      .then((res) => {
        elementBboxes = res.elements || [];
      })
      .catch(() => {
        elementBboxes = [];
      });

    try {
      const url = documentsApi.getFileUrl(documentId);
      const res = await fetch(url, { headers: authHeaders() });
      if (!res.ok) throw new Error(`Failed to load document file (HTTP ${res.status})`);
      const contentType = res.headers.get("content-type") || "";
      const disposition = res.headers.get("content-disposition") || "";
      const nameMatch = disposition.match(/filename="?([^";]+)"?/);
      filename = nameMatch?.[1] || `document-${documentId}`;
      const buffer = await res.arrayBuffer();

      const looksLikePdf = contentType.includes("pdf") || filename.toLowerCase().endsWith(".pdf");

      if (looksLikePdf) {
        try {
          isPdf = true;
          await openPdf(buffer);
          return;
        } catch (pdfErr: any) {
          // A genuinely malformed/corrupted PDF (broken xref/trailer, e.g.
          // pdf.js's "Invalid Root reference") can't be rendered at all —
          // fall back to whatever text was extracted at upload time instead
          // of showing a raw parser error.
          isPdf = false;
          pdfDoc = null;
          pdfFallbackNotice =
            "This PDF could not be rendered — it appears to be corrupted or malformed. Showing extracted text instead.";
          console.warn("PDF parsing failed, falling back to text panel", pdfErr);
        }
      }

      const detail = await documentsApi.get(documentId);
      plainText = detail.text || "";
      doclangXml = detail.doclang_xml || "";
      loading = false;
      if (pdfFallbackNotice && !plainText.trim()) {
        error =
          "This PDF could not be rendered, and no extracted text is available for it either.";
        pdfFallbackNotice = null;
      }
      queueMicrotask(scrollToHighlightInText);
    } catch (err: any) {
      error = err?.message || "Failed to load document.";
      loading = false;
    }
  }

  async function openPdf(buffer: ArrayBuffer) {
    const pdfjsLib = await import("pdfjs-dist");
    const workerUrl = (await import("pdfjs-dist/build/pdf.worker.mjs?url")).default;
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

    const doc = await pdfjsLib.getDocument({ data: buffer }).promise;
    pdfDoc = doc;
    pageCount = doc.numPages;
    currentPage = Math.min(Math.max(page || 1, 1), pageCount);
    pageInputValue = String(currentPage);
    loading = false;
    // canvasEl only mounts once Svelte flushes the DOM update from
    // `loading = false` (the template switches from the loading branch to
    // the canvas branch) — without this, renderCurrentPage() would run
    // against a not-yet-bound canvasEl and silently no-op.
    await tick();
    await renderCurrentPage();
  }

  function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => setTimeout(() => reject(new Error(message)), ms)),
    ]);
  }

  // ── Single-page rendering ───────────────────────────────────────────────

  async function renderCurrentPage() {
    if (!pdfDoc || !canvasEl) return;
    const myGeneration = renderGeneration;
    if (renderTask) {
      try {
        renderTask.cancel();
      } catch {
        // ignore — a stale render being cancelled is expected
      }
    }

    const pdfjsLib = await import("pdfjs-dist");
    const pdfPage = await pdfDoc.getPage(currentPage);
    if (myGeneration !== renderGeneration) return;
    const viewport = pdfPage.getViewport({ scale });
    updateBboxOverlay(viewport, currentPage);
    currentPageViewport = viewport;

    canvasEl.width = viewport.width;
    canvasEl.height = viewport.height;
    const ctx = canvasEl.getContext("2d");
    if (!ctx) return;

    renderTask = pdfPage.render({ canvasContext: ctx, viewport });
    try {
      await withTimeout(renderTask.promise, RENDER_TIMEOUT_MS, "Rendering this page took too long.");
    } catch (err: any) {
      if (err?.name === "RenderingCancelledException") return;
      if (myGeneration === renderGeneration) error = err?.message || "Failed to render this page.";
      return;
    }
    if (myGeneration !== renderGeneration) return;

    if (textLayerEl) {
      // textLayerEl is an opaque mount target handed to pdf.js's own TextLayer
      // builder (like IfcViewer's canvas container) — Svelte never reconciles
      // its children, so clearing it imperatively before each re-render is the
      // correct, intended usage rather than state Svelte should own.
      // eslint-disable-next-line svelte/no-dom-manipulating
      textLayerEl.innerHTML = "";
      textLayerEl.style.width = `${viewport.width}px`;
      textLayerEl.style.height = `${viewport.height}px`;
      try {
        const textContent = await pdfPage.getTextContent();
        const layer = new (pdfjsLib as any).TextLayer({
          textContentSource: textContent,
          container: textLayerEl,
          viewport,
        });
        await withTimeout(layer.render(), RENDER_TIMEOUT_MS, "Rendering the text layer took too long.");
        if (myGeneration === renderGeneration) highlightInTextLayer(textLayerEl);
      } catch {
        // Non-fatal: the page image itself already rendered above: losing the
        // text layer only means no selection/highlight overlay on this page.
      }
    }
  }

  // ── Continuous-scroll rendering (virtualized) ───────────────────────────

  async function setViewMode(mode: "single" | "continuous") {
    if (mode === viewMode || !pdfDoc) return;
    viewMode = mode;
    renderGeneration++;

    if (mode === "continuous") {
      if (pageSlots.length !== pageCount) {
        pageSlots = Array.from({ length: pageCount }, (_, i) => ({ pageNumber: i + 1, rendered: false }));
        pageSlotEls = new Array(pageCount);
        pageCanvasEls = new Array(pageCount);
        pageTextLayerEls = new Array(pageCount);
      } else {
        for (const slot of pageSlots) slot.rendered = false;
      }
      const firstPage = await pdfDoc.getPage(currentPage);
      const vp = firstPage.getViewport({ scale });
      estimatedPageWidth = vp.width;
      estimatedPageHeight = vp.height;
      await tick();
      setupContinuousObserver();
      await tick();
      pageSlotEls[currentPage - 1]?.scrollIntoView({ block: "start" });
    } else {
      teardownObserver();
      await tick();
      await renderCurrentPage();
    }
  }

  function setupContinuousObserver() {
    teardownObserver();
    if (!scrollContainerEl) return;
    intersectionObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const pageNumber = Number((entry.target as HTMLElement).dataset.page);
          if (!pageNumber) continue;
          const slot = pageSlots[pageNumber - 1];
          if (!slot) continue;
          if (entry.isIntersecting) {
            if (!slot.rendered) renderPageIntoSlot(pageNumber);
            if (entry.intersectionRatio > 0.5) {
              currentPage = pageNumber;
              pageInputValue = String(pageNumber);
            }
          } else if (slot.rendered) {
            unrenderSlot(pageNumber);
          }
        }
      },
      { root: scrollContainerEl, rootMargin: "800px 0px 800px 0px", threshold: [0, 0.5] },
    );
    for (const el of pageSlotEls) {
      if (el) intersectionObserver.observe(el);
    }
  }

  function teardownObserver() {
    intersectionObserver?.disconnect();
    intersectionObserver = null;
  }

  async function renderPageIntoSlot(pageNumber: number) {
    if (!pdfDoc) return;
    const myGeneration = renderGeneration;
    const canvas = pageCanvasEls[pageNumber - 1];
    const textLayerDiv = pageTextLayerEls[pageNumber - 1];
    if (!canvas) return;

    try {
      const pdfjsLib = await import("pdfjs-dist");
      const pdfPage = await pdfDoc.getPage(pageNumber);
      if (myGeneration !== renderGeneration) return;
      const viewport = pdfPage.getViewport({ scale });
      updateSlotBboxOverlay(viewport, pageNumber);
      slotViewports[pageNumber] = viewport;

      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const task = pdfPage.render({ canvasContext: ctx, viewport });
      await withTimeout(task.promise, RENDER_TIMEOUT_MS, "Rendering this page took too long.");
      if (myGeneration !== renderGeneration) return;

      if (textLayerDiv) {
        textLayerDiv.innerHTML = "";
        textLayerDiv.style.width = `${viewport.width}px`;
        textLayerDiv.style.height = `${viewport.height}px`;
        try {
          const textContent = await pdfPage.getTextContent();
          const layer = new (pdfjsLib as any).TextLayer({
            textContentSource: textContent,
            container: textLayerDiv,
            viewport,
          });
          await withTimeout(layer.render(), RENDER_TIMEOUT_MS, "Rendering the text layer took too long.");
          if (myGeneration === renderGeneration && highlightText) highlightInTextLayer(textLayerDiv);
        } catch {
          // Non-fatal — see renderCurrentPage's identical fallback.
        }
      }

      const slot = pageSlots[pageNumber - 1];
      if (slot && myGeneration === renderGeneration) slot.rendered = true;
    } catch {
      // Leave this one page unrendered (blank placeholder) rather than
      // failing the whole continuous-scroll view over one bad page.
    }
  }

  function unrenderSlot(pageNumber: number) {
    const canvas = pageCanvasEls[pageNumber - 1];
    const textLayerDiv = pageTextLayerEls[pageNumber - 1];
    if (canvas) {
      canvas.width = 0;
      canvas.height = 0;
    }
    if (textLayerDiv) textLayerDiv.innerHTML = "";
    const slot = pageSlots[pageNumber - 1];
    if (slot) slot.rendered = false;
    delete slotViewports[pageNumber];
  }

  // ── Zoom & page navigation (shared by both modes) ───────────────────────

  async function setScale(next: number) {
    const clamped = Math.min(MAX_SCALE, Math.max(MIN_SCALE, Math.round(next * 20) / 20));
    if (clamped === scale || !pdfDoc) return;
    scale = clamped;
    renderGeneration++;

    if (viewMode === "single") {
      await renderCurrentPage();
    } else {
      for (let i = 0; i < pageCanvasEls.length; i++) unrenderSlot(i + 1);
      const firstPage = await pdfDoc.getPage(currentPage);
      const vp = firstPage.getViewport({ scale });
      estimatedPageWidth = vp.width;
      estimatedPageHeight = vp.height;
      await tick();
      setupContinuousObserver();
    }
  }

  function zoomIn() {
    setScale(scale + SCALE_STEP);
  }
  function zoomOut() {
    setScale(scale - SCALE_STEP);
  }
  function zoomReset() {
    setScale(DEFAULT_SCALE);
  }

  async function goToPage(next: number) {
    const target = Math.min(Math.max(Math.trunc(next) || 1, 1), pageCount || 1);
    currentPage = target;
    pageInputValue = String(target);
    if (viewMode === "single") {
      await renderCurrentPage();
    } else {
      await tick();
      pageSlotEls[target - 1]?.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }

  function handlePageInputSubmit() {
    const n = parseInt(pageInputValue, 10);
    if (!Number.isNaN(n)) goToPage(n);
    else pageInputValue = String(currentPage);
  }

  // ── Highlighting ─────────────────────────────────────────────────────────

  /**
   * Build a case-insensitive regex from `text` that tolerates any amount of
   * whitespace difference between words (but nothing else) — a phrase that
   * spans a page/line break, or was re-flowed with different spacing between
   * extraction time and now, still matches as long as the words themselves
   * are unchanged.
   */
  function buildFlexibleMatcher(text: string): RegExp {
    const escaped = text.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(escaped.replace(/\s+/g, "\\s*"), "i");
  }

  function highlightInTextLayer(container: HTMLDivElement) {
    if (!highlightText) return;
    const trimmed = highlightText.trim();
    if (!trimmed) return;

    const spans = Array.from(container.querySelectorAll("span")) as HTMLSpanElement[];
    // Concatenate spans' raw text with NO injected separator — pdf.js's own
    // text-layer spans already carry any real whitespace as part of their
    // own content, and a phrase can legitimately split mid-run across two
    // spans with nothing between them (e.g. a kerning-driven span break).
    let raw = "";
    const ranges: { span: HTMLSpanElement; start: number; end: number }[] = [];
    for (const span of spans) {
      const text = span.textContent || "";
      const start = raw.length;
      raw += text;
      ranges.push({ span, start, end: start + text.length });
    }

    const match = buildFlexibleMatcher(trimmed).exec(raw);
    if (!match) return;
    const matchStart = match.index;
    const matchEnd = matchStart + match[0].length;

    let firstMatch: HTMLSpanElement | null = null;
    for (const { span, start, end } of ranges) {
      if (end > matchStart && start < matchEnd) {
        span.classList.add("bg-amber-400/60", "rounded-sm");
        if (!firstMatch) firstMatch = span;
      }
    }
    firstMatch?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  function scrollToHighlightInText() {
    if (!textPanelEl || !highlightText) return;
    const mark = textPanelEl.querySelector("mark");
    mark?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  interface HighlightSplit {
    before: string;
    match: string;
    after: string;
  }

  function splitOnHighlight(text: string, highlight: string | null | undefined): HighlightSplit | null {
    if (!highlight) return null;
    const trimmed = highlight.trim();
    if (!trimmed) return null;
    const match = buildFlexibleMatcher(trimmed).exec(text);
    if (!match) return null;
    return {
      before: text.slice(0, match.index),
      match: match[0],
      after: text.slice(match.index + match[0].length),
    };
  }

  let highlightSplit = $derived(splitOnHighlight(plainText, highlightText));

  onMount(() => {
    loadOverlayPrefs();
    load();
  });

  onDestroy(() => {
    teardownObserver();
    try {
      renderTask?.cancel();
    } catch {
      // ignore
    }
    pdfDoc?.destroy?.();
  });

  $effect(() => {
    if (documentId !== loadedDocumentId) {
      load();
    }
  });
</script>

<svelte:document
  onclick={() => {
    overlaySettingsOpen = false;
    viewsMenuOpen = false;
    layersMenuOpen = false;
  }}
/>

<div class="flex h-full min-h-[60vh] flex-col">
  {#if loading}
    <div class="flex flex-1 items-center justify-center">
      <LoadingState message="Loading document…" />
    </div>
  {:else if error}
    <div class="flex flex-1 items-center justify-center">
      <EmptyState title="Couldn't load document" description={error} icon={AlertCircle} />
    </div>
  {:else}
    {#if doclangLoadError && !doclangXml}
      <div
        class="flex shrink-0 items-center gap-2 border-b border-amber-900/60 bg-amber-950/30 px-4 py-2 text-xs text-amber-300"
      >
        <AlertCircle class="h-3.5 w-3.5 shrink-0" />
        <span>DocLang content unavailable — {doclangLoadError}</span>
      </div>
    {/if}
    {#if doclangXml}
      <div class="flex shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 px-4 py-2">
        <div class="relative">
          <button
            type="button"
            onclick={(e) => (e.stopPropagation(), (viewsMenuOpen = !viewsMenuOpen))}
            aria-expanded={viewsMenuOpen}
            aria-haspopup="true"
            class="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          >
            <span>Views</span>
            <ChevronDown class="h-3 w-3" />
          </button>
          {#if viewsMenuOpen}
            <div
              role="none"
              onclick={(e) => e.stopPropagation()}
              class="absolute left-0 top-full z-40 mt-2 w-48 space-y-1 rounded-xl border border-slate-800 bg-slate-900 p-1.5 text-xs shadow-xl"
            >
              <label class="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-800">
                <span class="text-slate-200">Original Page</span>
                <input type="checkbox" bind:checked={showOriginalPage} />
              </label>
              <label class="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-800">
                <span class="text-slate-200">DocLang</span>
                <input type="checkbox" bind:checked={showDoclangPane} />
              </label>
              <label class="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-800">
                <span class="text-slate-200">Reading View</span>
                <input type="checkbox" bind:checked={showReadingPane} />
              </label>
            </div>
          {/if}
        </div>

        <div class="flex items-center gap-2">
          <button
            type="button"
            onclick={downloadDoclangArchive}
            class="inline-flex items-center gap-1.5 rounded-lg border border-cyan-800/60 bg-cyan-950/30 px-2.5 py-1 text-xs font-medium text-cyan-200 transition-colors hover:bg-cyan-900/50 hover:text-white"
            title="Export DocLang Archive (.dclx) package compatible with official DocLang Viewer"
          >
            <Download class="h-3.5 w-3.5 text-cyan-400" />
            <span>Export .dclx</span>
          </button>
        </div>
      </div>
    {/if}

    {#snippet readingViewContent()}
      {#if documentBlocks.length === 0}
        <div class="flex flex-col items-center justify-center py-16 text-center text-slate-400">
          <FileCode class="mb-2 h-10 w-10 text-slate-600" />
          <p class="text-sm font-semibold text-slate-300">No Renderable Content</p>
          <p class="mt-1 max-w-md text-xs text-slate-500">
            The document was parsed into DocLang XML, but no headings, paragraphs, lists, or tables could be extracted from it.
          </p>
        </div>
      {:else if readingBlocks.length === 0}
        <div class="flex flex-col items-center justify-center py-16 text-center text-slate-400">
          <FileCode class="mb-2 h-10 w-10 text-slate-600" />
          <p class="text-sm font-semibold text-slate-300">Everything is hidden</p>
          <p class="mt-1 max-w-md text-xs text-slate-500">
            All of this document's content is furniture/background and currently hidden — turn on the Layers toggles above to show it.
          </p>
        </div>
      {:else}
        <div class="mx-auto max-w-3xl space-y-4">
          {#each visibleBlocks as block, bIdx (bIdx)}
                  {#if block.type === "heading"}
                    <div
                      data-element-id={block.elementId}
                      onclick={() => block.elementId && selectElement(block.elementId)}
                      role="presentation"
                      class="rounded-lg {block.layer !== 'body' ? 'border border-dashed border-slate-700/70 bg-slate-950/40 p-2' : ''} {block.elementId
                        ? 'cursor-pointer'
                        : ''} {block.elementId && block.elementId === selectedElementId
                        ? 'bg-accent/10 ring-1 ring-accent/50'
                        : ''}"
                    >
                      {#if block.layer !== "body"}
                        <span class="mr-2 rounded bg-slate-800 px-1.5 py-0.5 align-middle text-[10px] uppercase tracking-wide text-slate-500">{block.layer}</span>
                      {/if}
                      <svelte:element
                        this={`h${block.level}`}
                        class="inline font-semibold text-slate-100 {block.level === 1
                          ? 'text-lg'
                          : block.level === 2
                            ? 'text-base'
                            : 'text-sm'}"
                      >
                        {block.text}
                      </svelte:element>
                    </div>
                  {:else if block.type === "paragraph"}
                    <p
                      data-element-id={block.elementId}
                      onclick={() => block.elementId && selectElement(block.elementId)}
                      role="presentation"
                      class="whitespace-pre-wrap rounded-lg text-sm leading-relaxed text-slate-300 {block.layer !== 'body'
                        ? 'border border-dashed border-slate-700/70 bg-slate-950/40 p-2'
                        : ''} {block.elementId ? 'cursor-pointer' : ''} {block.elementId &&
                      block.elementId === selectedElementId
                        ? 'bg-accent/10 ring-1 ring-accent/50'
                        : ''}"
                    >
                      {#if block.layer !== "body"}
                        <span class="mr-2 rounded bg-slate-800 px-1.5 py-0.5 align-middle text-[10px] uppercase tracking-wide text-slate-500">{block.layer}</span>
                      {/if}
                      {block.text}
                    </p>
                  {:else if block.type === "list"}
                    <ul class="list-disc space-y-1 pl-5 text-sm text-slate-300">
                      {#each block.items as item, iIdx (iIdx)}
                        <li>{item}</li>
                      {/each}
                    </ul>
                  {:else if block.type === "table"}
                    <div
                      data-element-id={block.elementId}
                      onclick={() => block.elementId && selectElement(block.elementId)}
                      role="presentation"
                      class="overflow-hidden rounded-xl border shadow-lg {block.elementId
                        ? 'cursor-pointer'
                        : ''} {block.elementId && block.elementId === selectedElementId
                        ? 'border-accent/60 bg-accent/5 ring-1 ring-accent/50'
                        : 'border-slate-800 bg-slate-950/60'}"
                    >
                      <div class="flex items-center justify-between border-b border-slate-800 bg-slate-900/60 px-4 py-2.5">
                        <span class="text-xs font-semibold text-slate-200">{block.title}</span>
                        <span class="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400">
                          {block.rows.length} rows × {block.rows[0]?.length || 0} cols
                        </span>
                      </div>
                      <div class="overflow-x-auto p-3">
                        <table class="w-full text-left text-xs text-slate-300">
                          {#if block.rows.length > 0}
                            <thead class="border-b border-slate-800 bg-slate-900/90 font-semibold uppercase text-caption text-slate-400">
                              <tr>
                                {#each block.rows[0] as colHeader, colIdx (colIdx)}
                                  <th class="px-3 py-2">{colHeader || `Col ${colIdx + 1}`}</th>
                                {/each}
                              </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800/60 font-mono text-xs">
                              {#each block.rows.slice(1) as row, rowIdx (rowIdx)}
                                <tr class="hover:bg-slate-900/40">
                                  {#each row as cell, cellIdx (cellIdx)}
                                    <td class="px-3 py-2 text-slate-200">{cell}</td>
                                  {/each}
                                </tr>
                              {/each}
                            </tbody>
                          {/if}
                        </table>
                      </div>
                    </div>
                  {:else if block.type === "image"}
                    <figure
                      data-element-id={block.elementId}
                      onclick={() => block.elementId && selectElement(block.elementId)}
                      role="presentation"
                      class="overflow-hidden rounded-xl border p-3 {block.elementId ? 'cursor-pointer' : ''} {block.elementId &&
                      block.elementId === selectedElementId
                        ? 'border-accent/60 bg-accent/5 ring-1 ring-accent/50'
                        : 'border-slate-800 bg-slate-950/60'}"
                    >
                      <img
                        src={block.src}
                        alt={block.alt || "Embedded document picture"}
                        loading="lazy"
                        class="mx-auto max-h-[32rem] rounded-lg object-contain"
                        onerror={(e) => ((e.currentTarget as HTMLImageElement).classList.add("opacity-30"))}
                      />
                      {#if block.alt}
                        <figcaption class="mt-2 text-center text-xs text-slate-400">{block.alt}</figcaption>
                      {/if}
                    </figure>
                  {:else if block.type === "page-break"}
                    <div class="flex items-center gap-3 py-1" role="separator" aria-label="Page {block.pageNumber}">
                      <div class="h-px flex-1 bg-slate-800"></div>
                      <span class="shrink-0 text-caption font-semibold uppercase tracking-widest text-slate-600"
                        >Page {block.pageNumber}</span
                      >
                      <div class="h-px flex-1 bg-slate-800"></div>
                    </div>
                  {/if}
                {/each}
          {#if visibleBlockCount < readingBlocks.length}
            <div bind:this={blocksSentinelEl} class="flex justify-center py-4">
              <span class="text-caption text-slate-500">Loading more…</span>
            </div>
          {/if}
        </div>
      {/if}
    {/snippet}

    {#snippet originalPageContent()}
      {#if isPdf}
      <div class="flex flex-1 flex-col overflow-hidden">
        <div
          class="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-slate-950 px-3 py-2"
        >
          <div class="flex items-center gap-1">
            <button
              type="button"
              onclick={zoomOut}
              disabled={scale <= MIN_SCALE}
              class="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
              aria-label="Zoom out"
            >
              <ZoomOut class="h-4 w-4" />
            </button>
            <button
              type="button"
              onclick={zoomReset}
              class="min-w-[3.5rem] rounded-lg px-1.5 py-1 text-center text-xs text-slate-300 hover:bg-slate-800"
              title="Reset zoom"
            >
              {Math.round((scale / DEFAULT_SCALE) * 100)}%
            </button>
            <button
              type="button"
              onclick={zoomIn}
              disabled={scale >= MAX_SCALE}
              class="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
              aria-label="Zoom in"
            >
              <ZoomIn class="h-4 w-4" />
            </button>
            <button
              type="button"
              onclick={zoomReset}
              class="ml-0.5 rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              aria-label="Reset zoom and layout"
              title="Reset"
            >
              <RotateCcw class="h-3.5 w-3.5" />
            </button>
          </div>

          <div class="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900 p-0.5">
            <button
              type="button"
              onclick={() => setViewMode("single")}
              class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors {viewMode === 'single'
                ? 'bg-accent text-white'
                : 'text-slate-400 hover:text-slate-200'}"
            >
              Single Page
            </button>
            <button
              type="button"
              onclick={() => setViewMode("continuous")}
              class="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors {viewMode ===
              'continuous'
                ? 'bg-accent text-white'
                : 'text-slate-400 hover:text-slate-200'}"
            >
              <Rows3 class="h-3 w-3" />
              <span>Continuous</span>
            </button>
          </div>

          {#if elementBboxes.length > 0}
            <div class="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900 p-0.5">
              <button
                type="button"
                onclick={() => (showBboxOverlay = !showBboxOverlay)}
                title="Toggle per-element bounding boxes"
                class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors {showBboxOverlay
                  ? 'bg-accent text-white'
                  : 'text-slate-400 hover:text-slate-200'}"
              >
                Boxes
              </button>
              <button
                type="button"
                onclick={() => (showReadingOrderArrows = !showReadingOrderArrows)}
                title="Toggle reading-order arrows"
                class="rounded-md px-2.5 py-1 text-xs font-medium transition-colors {showReadingOrderArrows
                  ? 'bg-accent text-white'
                  : 'text-slate-400 hover:text-slate-200'}"
              >
                Reading order
              </button>
              <div class="relative">
                <button
                  type="button"
                  onclick={(e) => (e.stopPropagation(), (overlaySettingsOpen = !overlaySettingsOpen))}
                  title="Overlay settings"
                  aria-expanded={overlaySettingsOpen}
                  class="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-200"
                >
                  <Settings2 class="h-3.5 w-3.5" />
                </button>
                {#if overlaySettingsOpen}
                  <div
                    role="none"
                    onclick={(e) => e.stopPropagation()}
                    class="absolute right-0 top-full z-40 mt-2 w-64 space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-3 text-xs shadow-xl"
                  >
                    <label class="flex items-center justify-between gap-2">
                      <span class="font-medium text-slate-200">Badges</span>
                      <input type="checkbox" bind:checked={showElementBadges} />
                    </label>
                    <div class="border-t border-slate-800 pt-2">
                      <p class="mb-2 font-medium text-slate-200">Reading-order arrow style</p>
                      <div class="space-y-2">
                        <label class="flex items-center justify-between gap-2">
                          <span class="text-slate-400">Color</span>
                          <input type="color" bind:value={arrowColor} class="h-6 w-10 rounded border border-slate-700 bg-slate-950" />
                        </label>
                        <label class="flex items-center justify-between gap-2">
                          <span class="text-slate-400">Thickness</span>
                          <input type="range" min="0.5" max="6" step="0.5" bind:value={arrowWidth} class="w-28" />
                        </label>
                        <label class="flex items-center justify-between gap-2">
                          <span class="text-slate-400">Head size</span>
                          <input type="range" min="3" max="14" step="1" bind:value={arrowHead} class="w-28" />
                        </label>
                        <label class="flex items-center justify-between gap-2">
                          <span class="text-slate-400">Line</span>
                          <select
                            bind:value={arrowLineStyle}
                            class="rounded border border-slate-700 bg-slate-950 px-1.5 py-0.5 text-slate-200"
                          >
                            <option value="solid">Solid</option>
                            <option value="dashed">Dashed</option>
                            <option value="dotted">Dotted</option>
                          </select>
                        </label>
                      </div>
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          {#if pageCount > 1}
            <div class="flex items-center gap-1.5">
              <button
                type="button"
                onclick={() => goToPage(currentPage - 1)}
                disabled={currentPage <= 1}
                class="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
                aria-label="Previous page"
              >
                <ChevronLeft class="h-4 w-4" />
              </button>
              <input
                type="text"
                inputmode="numeric"
                bind:value={pageInputValue}
                onkeydown={(e) => e.key === "Enter" && handlePageInputSubmit()}
                onblur={handlePageInputSubmit}
                class="w-12 rounded-lg border border-slate-700 bg-slate-950 px-1.5 py-1 text-center text-xs text-slate-100 focus:border-accent focus:outline-none"
                aria-label="Page number"
              />
              <span class="text-xs text-slate-400">of {pageCount}</span>
              <button
                type="button"
                onclick={() => goToPage(currentPage + 1)}
                disabled={currentPage >= pageCount}
                class="rounded-lg p-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-30"
                aria-label="Next page"
              >
                <ChevronRight class="h-4 w-4" />
              </button>
            </div>
          {/if}
        </div>

        {#if viewMode === "single"}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            bind:this={singlePageScrollEl}
            role="region"
            aria-label="PDF page, draggable to pan when zoomed in"
            onpointerdown={(e) => onPanPointerDown(e, singlePageScrollEl)}
            onpointermove={onPanPointerMove}
            onpointerup={onPanPointerUp}
            onpointercancel={onPanPointerUp}
            class="relative flex flex-1 items-start justify-center overflow-auto bg-slate-950/60 p-4 {isPanning
              ? 'cursor-grabbing select-none'
              : 'cursor-grab'}"
          >
            <div class="relative shadow-2xl">
              <canvas bind:this={canvasEl} class="block rounded-lg bg-white"></canvas>
              <div bind:this={textLayerEl} class="pdf-text-layer"></div>
              {#if currentPageViewport && (elementBboxes.length > 0)}
                <PdfElementOverlay
                  elements={elementBboxes}
                  pageNumber={currentPage}
                  viewport={currentPageViewport}
                  width={canvasEl?.width ?? 0}
                  height={canvasEl?.height ?? 0}
                  {selectedElementId}
                  onSelect={selectElement}
                  showBoxes={showBboxOverlay}
                  showReadingOrder={showReadingOrderArrows}
                  elementLayers={elementLayerMap}
                  showBadges={showElementBadges}
                  arrowStyle={arrowStyleValue}
                  tooltipText={elementTooltipText}
                />
              {/if}
              {#if activeBboxRect}
                <div
                  class="pointer-events-none absolute rounded border-2 border-cyan-400 bg-cyan-400/20 shadow-[0_0_15px_rgba(6,182,212,0.6)] transition-all duration-300 animate-pulse"
                  style="left: {activeBboxRect.left}px; top: {activeBboxRect.top}px; width: {activeBboxRect.width}px; height: {activeBboxRect.height}px;"
                >
                  <span class="absolute -top-5 left-0 rounded bg-cyan-500 px-1.5 py-0.5 text-[10px] font-bold text-slate-950 shadow">
                    Source Clause
                  </span>
                </div>
              {/if}
            </div>
          </div>
        {:else}
          <div
            bind:this={scrollContainerEl}
            class="flex flex-1 flex-col items-center gap-4 overflow-y-auto bg-slate-950/60 p-4"
          >
            {#each pageSlots as slot (slot.pageNumber)}
              <div
                bind:this={pageSlotEls[slot.pageNumber - 1]}
                class="relative shadow-2xl"
                style="min-width: {estimatedPageWidth ? `${estimatedPageWidth}px` : 'auto'}; min-height: {estimatedPageHeight ? `${estimatedPageHeight}px` : '400px'};"
              >
                <canvas
                  bind:this={pageCanvasEls[slot.pageNumber - 1]}
                  class="block rounded-lg bg-white"
                ></canvas>
                <div
                  bind:this={pageTextLayerEls[slot.pageNumber - 1]}
                  class="pdf-text-layer"
                ></div>
                {#if slotViewports[slot.pageNumber] && elementBboxes.length > 0}
                  <PdfElementOverlay
                    elements={elementBboxes}
                    pageNumber={slot.pageNumber}
                    viewport={slotViewports[slot.pageNumber]}
                    width={pageCanvasEls[slot.pageNumber - 1]?.width ?? 0}
                    height={pageCanvasEls[slot.pageNumber - 1]?.height ?? 0}
                    {selectedElementId}
                    onSelect={selectElement}
                    showBoxes={showBboxOverlay}
                    showReadingOrder={showReadingOrderArrows}
                    elementLayers={elementLayerMap}
                    showBadges={showElementBadges}
                    arrowStyle={arrowStyleValue}
                    tooltipText={elementTooltipText}
                  />
                {/if}
                {#if slotBboxRects[slot.pageNumber]}
                  <div
                    class="pointer-events-none absolute rounded border-2 border-cyan-400 bg-cyan-400/20 shadow-[0_0_15px_rgba(6,182,212,0.6)] transition-all duration-300 animate-pulse"
                    style="left: {slotBboxRects[slot.pageNumber].left}px; top: {slotBboxRects[slot.pageNumber].top}px; width: {slotBboxRects[slot.pageNumber].width}px; height: {slotBboxRects[slot.pageNumber].height}px;"
                  >
                    <span class="absolute -top-5 left-0 rounded bg-cyan-500 px-1.5 py-0.5 text-[10px] font-bold text-slate-950 shadow">
                      Source Clause
                    </span>
                  </div>
                {/if}
                {#if !slot.rendered}
                  <div class="absolute inset-0 flex items-center justify-center rounded-lg bg-slate-900/40 text-micro text-slate-500">
                    Page {slot.pageNumber}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div class="flex flex-1 flex-col overflow-hidden">
        {#if pdfFallbackNotice}
          <div class="flex shrink-0 items-start gap-2 border-b border-amber-800/50 bg-amber-950/40 px-4 py-2.5 text-xs text-amber-300">
            <FileIcon class="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{pdfFallbackNotice}</span>
          </div>
        {/if}
        <div
          bind:this={textPanelEl}
          class="flex-1 overflow-y-auto whitespace-pre-wrap bg-slate-950/60 p-6 font-mono text-xs leading-relaxed text-slate-300"
        >
          {#if highlightSplit}
            {highlightSplit.before}<mark class="rounded-sm bg-amber-400/60 text-slate-950">{highlightSplit.match}</mark
            >{highlightSplit.after}
          {:else}
            {plainText || "No extracted text found."}
          {/if}
        </div>
      </div>
      {/if}
    {/snippet}

    <!-- Three synchronized panes -- Original Page (PDF or text fallback),
         DocLang (raw XML), Reading View (rendered blocks) -- all visible at
         once so a click/hover in one highlights the matching element in the
         others, instead of the old single-active-tab switcher. Collapses to
         just Original Page (full width) when there's no DocLang XML at all. -->
    {#if doclangXml}
      <div class="flex flex-1 overflow-x-auto overflow-y-hidden">
        {#if showOriginalPage}
          <div class="flex min-w-[320px] flex-1 flex-col overflow-hidden border-r border-slate-800">
            <div class="flex shrink-0 items-center border-b border-slate-800 bg-slate-950 px-3 py-1.5">
              <span class="text-caption font-semibold uppercase tracking-wide text-slate-500">Original Page</span>
            </div>
            {@render originalPageContent()}
          </div>
        {/if}
        {#if showDoclangPane}
          <div class="flex min-w-[320px] flex-1 flex-col overflow-hidden border-r border-slate-800">
            <div class="flex shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 px-3 py-1.5">
              <div class="flex items-center gap-2">
                <span class="text-caption font-semibold uppercase tracking-wide text-slate-500">DocLang</span>
                {#if parsedTables.length > 0}
                  <span class="rounded-full bg-cyan-950 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-300">
                    {parsedTables.length} {parsedTables.length === 1 ? "table" : "tables"}
                  </span>
                {/if}
              </div>
              <button
                type="button"
                onclick={copyXmlToClipboard}
                class="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-700 hover:text-white"
              >
                {#if copiedXml}
                  <Check class="h-3 w-3 text-emerald-400" />
                  <span class="text-emerald-400">Copied!</span>
                {:else}
                  <Copy class="h-3 w-3" />
                  <span>Copy XML</span>
                {/if}
              </button>
            </div>
            <div class="flex-1 overflow-y-auto p-2">
              <DocLangXmlTree xml={doclangXml} {selectedElementId} onSelect={selectElement} />
            </div>
          </div>
        {/if}
        {#if showReadingPane}
          <div class="flex min-w-[320px] flex-1 flex-col overflow-hidden">
            <div class="flex shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 px-3 py-1.5">
              <span class="text-caption font-semibold uppercase tracking-wide text-slate-500">Reading View</span>
              {#if documentBlocks.some((b) => "layer" in b && b.layer !== "body")}
                <div class="relative">
                  <button
                    type="button"
                    onclick={(e) => (e.stopPropagation(), (layersMenuOpen = !layersMenuOpen))}
                    aria-expanded={layersMenuOpen}
                    aria-haspopup="true"
                    class="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-700 hover:text-white"
                  >
                    <span>Layers</span>
                    <ChevronDown class="h-3 w-3" />
                  </button>
                  {#if layersMenuOpen}
                    <div
                      role="none"
                      onclick={(e) => e.stopPropagation()}
                      class="absolute right-0 top-full z-40 mt-2 w-44 space-y-1 rounded-xl border border-slate-800 bg-slate-900 p-2 text-xs shadow-xl"
                    >
                      <label class="flex items-center justify-between gap-2 rounded-md px-1.5 py-1 hover:bg-slate-800">
                        <span class="text-slate-200">Furniture</span>
                        <input type="checkbox" bind:checked={showReadingFurniture} />
                      </label>
                      <label class="flex items-center justify-between gap-2 rounded-md px-1.5 py-1 hover:bg-slate-800">
                        <span class="text-slate-200">Background</span>
                        <input type="checkbox" bind:checked={showReadingBackground} />
                      </label>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
            <div class="flex-1 overflow-y-auto p-4">
              {@render readingViewContent()}
            </div>
          </div>
        {/if}
      </div>
    {:else}
      {@render originalPageContent()}
    {/if}
  {/if}
</div>

<style>
  /* Standard pdf.js text-layer positioning — spans are transparent and laid
     out to match the canvas glyphs exactly, so selection/highlighting lines
     up with what's visually rendered underneath. */
  .pdf-text-layer {
    position: absolute;
    inset: 0;
    overflow: hidden;
    line-height: 1;
    text-align: initial;
    transform-origin: 0 0;
  }
  .pdf-text-layer :global(span),
  .pdf-text-layer :global(br) {
    color: transparent;
    position: absolute;
    white-space: pre;
    cursor: text;
    transform-origin: 0% 0%;
  }
</style>
