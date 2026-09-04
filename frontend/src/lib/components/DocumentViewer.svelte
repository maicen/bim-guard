<script lang="ts">
  import { onMount, onDestroy, tick } from "svelte";
  import {
    ChevronLeft,
    ChevronRight,
    Loader2,
    AlertCircle,
    ZoomIn,
    ZoomOut,
    RotateCcw,
    Rows3,
    FileText as FileIcon,
  } from "lucide-svelte";
  import { documentsApi } from "../api";

  interface Props {
    documentId: number;
    /** 1-based page to open on, when known (from GET /api/rules/{id}/source). */
    page?: number | null;
    /** Source snippet to highlight — matched against the PDF text layer, or the plain-text panel for non-PDF documents. */
    highlightText?: string | null;
  }

  let { documentId, page = null, highlightText = null }: Props = $props();

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

  let loadedDocumentId: number | null = null;

  async function load() {
    if (loadedDocumentId === documentId) return;
    loadedDocumentId = documentId;
    loading = true;
    error = null;
    pdfFallbackNotice = null;
    pdfDoc = null;
    isPdf = false;
    plainText = "";
    viewMode = "single";
    scale = DEFAULT_SCALE;
    teardownObserver();
    pageSlots = [];

    try {
      const url = documentsApi.getFileUrl(documentId);
      const res = await fetch(url);
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
      plainText = detail.extracted_text || "";
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

<div class="flex h-full min-h-[60vh] flex-col">
  {#if loading}
    <div class="flex flex-1 items-center justify-center gap-2 text-sm text-slate-400">
      <Loader2 class="h-5 w-5 animate-spin" />
      <span>Loading document…</span>
    </div>
  {:else if error}
    <div class="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-red-400">
      <AlertCircle class="h-6 w-6" />
      <span>{error}</span>
    </div>
  {:else if isPdf}
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
        <div class="flex-1 overflow-auto bg-slate-950/60 p-4">
          <div class="relative mx-auto w-fit">
            <canvas bind:this={canvasEl} class="block rounded-lg shadow-lg"></canvas>
            <div bind:this={textLayerEl} class="pdf-text-layer"></div>
          </div>
        </div>
      {:else}
        <div bind:this={scrollContainerEl} class="flex-1 overflow-auto bg-slate-950/60 p-4">
          <div class="mx-auto flex w-fit flex-col gap-4">
            {#each pageSlots as slot, i (slot.pageNumber)}
              <div
                bind:this={pageSlotEls[i]}
                data-page={slot.pageNumber}
                class="relative"
                style="min-width: {estimatedPageWidth}px; min-height: {estimatedPageHeight}px;"
              >
                <canvas bind:this={pageCanvasEls[i]} class="block rounded-lg shadow-lg"></canvas>
                <div bind:this={pageTextLayerEls[i]} class="pdf-text-layer"></div>
                {#if !slot.rendered}
                  <div class="absolute inset-0 flex items-center justify-center rounded-lg bg-slate-900/40 text-micro text-slate-500">
                    Page {slot.pageNumber}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
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
